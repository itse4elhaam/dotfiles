const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {join} = require('node:path');
const TabRecorder = new Function(readFileSync(join(__dirname, 'recorder.js'), 'utf8') + '; return TabRecorder;')();
global.cancelAnimationFrame = () => {};
class Track {
  constructor(kind) { this.kind = kind; this.readyState = 'live'; this.listeners = []; this.stops = 0; }
  addEventListener(type, callback) { if (type === 'ended') this.listeners.push(callback); }
  stop() { this.stops++; this.readyState = 'ended'; }
  end() { this.readyState = 'ended'; this.listeners.forEach(fn => fn()); }
}
class Stream {
  constructor(tracks = []) { this.tracks = tracks; }
  getTracks() { return this.tracks; }
  getVideoTracks() { return this.tracks.filter(t => t.kind === 'video'); }
  getAudioTracks() { return this.tracks.filter(t => t.kind === 'audio'); }
}
global.MediaStream = Stream;
class Recorder {
  static isTypeSupported(type) { return type.includes('vp8'); }
  constructor(stream, options) { this.stream = stream; this.options = options; this.state = 'inactive'; }
  start() { this.state = 'recording'; }
  stop() { this.state = 'inactive'; this.ondataavailable({data:new Blob(['video'])}); this.onstop(); }
}
function fixture(stream = new Stream([new Track('video')])) {
  const calls = [], messages = [], saved = [], cancelled = [];
  let picker;
  const api = {chooseDesktopMedia(sources, callback) { calls.push(sources); picker = callback; return 8; },
    cancelChooseDesktopMedia(id) { cancelled.push(id); }};
  const requests = [];
  const media = {async getUserMedia(constraints) { requests.push(constraints); return stream; }};
  const recorder = new TabRecorder(api,media,Recorder, text => messages.push(text), blob => saved.push(blob));
  return {recorder,media,stream,calls,messages,saved,cancelled,requests, choose:(id='selected',options={}) => picker(id,options)};
}
test('no picker or capture on construction; tab only with consent gated audio and supported codec', async () => {
  const f = fixture(); assert.deepEqual(f.calls,[]); assert.deepEqual(f.requests,[]);
  const start = f.recorder.start({audio:true});
  assert.deepEqual(f.calls,[['tab','audio']]);
  f.choose('selected',{canRequestAudioTrack:false}); await start;
  assert.equal(f.requests[0].audio,false);
  assert.equal(f.requests[0].video.mandatory.chromeMediaSourceId,'selected');
  assert.equal(f.recorder.recorder.options.mimeType,'video/webm;codecs=vp8,opus');
  assert.match(f.messages.at(-1), /not shared/);
  f.recorder.stop(); assert.equal(f.saved.length,1);
  assert.equal(f.stream.getTracks()[0].stops,1);
});
test('picker denied/cancelled never requests a stream', async () => {
  const f = fixture(); const start = f.recorder.start(); f.choose(''); await start;
  assert.deepEqual(f.calls,[['tab']]); assert.equal(f.requests.length,0); assert.equal(f.saved.length,0);
  assert.equal(f.recorder.state,'idle');
});
test('stop cancels picker and ignores its late completion', async () => {
  const f = fixture(); const start = f.recorder.start(); f.recorder.stop(); f.choose(); await start;
  assert.deepEqual(f.cancelled,[8]); assert.equal(f.requests.length,0);
});
test('late getUserMedia result is stopped after cancellation', async () => {
  const f = fixture(); let resolve;
  f.media.getUserMedia = () => new Promise(done => { resolve = done; });
  const start = f.recorder.start(); f.choose(); await Promise.resolve();
  f.recorder.stop(); resolve(f.stream); await start;
  assert.equal(f.stream.getTracks()[0].stops,1); assert.equal(f.saved.length,0);
});
test('revoked or closed tab finalizes data and releases every source', async () => {
  const f = fixture(new Stream([new Track('video'),new Track('audio')]));
  const start = f.recorder.start({audio:true}); f.choose('selected',{canRequestAudioTrack:true}); await start;
  assert.notEqual(f.requests[0].audio,false);
  f.stream.getVideoTracks()[0].end();
  assert.equal(f.saved.length,1); assert.equal(f.recorder.state,'idle');
  assert.ok(f.stream.getTracks().every(t => t.stops === 1));
});
test('missing shared audio or video fails without fallback', async () => {
  for (const tracks of [[new Track('video')], [new Track('audio')], []]) {
    const f = fixture(new Stream(tracks)); const start = f.recorder.start({audio:true});
    f.choose('selected',{canRequestAudioTrack:true}); await start;
    assert.equal(f.requests.length,1); assert.equal(f.recorder.state,'idle'); assert.equal(f.saved.length,0);
    assert.ok(tracks.every(t => t.stops === 1));
  }
});
test('microphone/camera permission denial releases the already chosen tab', async () => {
  for (const optional of ['mic','camera']) {
    const f = fixture(); let requests = 0;
    f.media.getUserMedia = async () => { if (++requests === 1) return f.stream; throw new Error('Permission denied'); };
    const start = f.recorder.start({[optional]:true}); f.choose(); await start;
    assert.equal(requests,2); assert.equal(f.stream.getTracks()[0].stops,1);
    assert.equal(f.saved.length,0); assert.equal(f.recorder.state,'idle');
  }
});
test('tab loss while device permission is pending releases late device and never records', async () => {
  const f = fixture(); const microphone = new Stream([new Track('audio')]);
  let resolve, requests = 0;
  f.media.getUserMedia = async () => ++requests === 1 ? f.stream : new Promise(done => { resolve = done; });
  const start = f.recorder.start({mic:true}); f.choose();
  for (let n=0;n<5;n++) await Promise.resolve();
  f.stream.getVideoTracks()[0].end(); resolve(microphone); await start;
  assert.equal(microphone.getTracks()[0].stops,1); assert.equal(f.saved.length,0);
});
test('denied getUserMedia does not retry or fallback', async () => {
  const f = fixture(); let requests = 0;
  f.media.getUserMedia = async () => { requests++; throw new Error('Permission denied'); };
  const start = f.recorder.start(); f.choose(); await start;
  assert.equal(requests,1); assert.equal(f.saved.length,0); assert.equal(f.recorder.state,'idle');
});
test('optional mic is mixed with consented tab audio and all tracks/context are released', async () => {
  const destination = new Stream([new Track('audio')]);
  let closed = 0, connections = 0;
  global.AudioContext = class {
    async resume() {} close() { closed++; }
    createMediaStreamDestination() { return {stream:destination}; }
    createMediaStreamSource() { return {connect() { connections++; }}; }
  };
  const f = fixture(new Stream([new Track('video'),new Track('audio')]));
  const mic = new Stream([new Track('audio')]); let count = 0;
  f.media.getUserMedia = async () => ++count === 1 ? f.stream : mic;
  const start = f.recorder.start({audio:true,mic:true}); f.choose('selected',{canRequestAudioTrack:true}); await start;
  assert.equal(connections,2); assert.equal(f.recorder.recorder.stream.getAudioTracks().length,1);
  f.recorder.stop(); assert.equal(closed,1);
  assert.ok([...f.stream.getTracks(),...mic.getTracks(),...destination.getTracks()].every(t => t.stops === 1));
});
test('optional camera composites one tab image with one camera and releases canvas sources', async () => {
  const canvasStream = new Stream([new Track('video')]);
  let draws = 0, paused = 0;
  const ctx = {drawImage() { draws++; },save(){},beginPath(){},arc(){},clip(){},restore(){}};
  global.requestAnimationFrame = () => 42;
  global.document = {createElement(kind) {
    if (kind === 'video') return {videoWidth:640,videoHeight:480,async play(){},pause(){paused++;}};
    return {getContext:() => ctx,captureStream:() => canvasStream};
  }};
  const f = fixture(), webcam = new Stream([new Track('video')]); let count = 0;
  f.media.getUserMedia = async () => ++count === 1 ? f.stream : webcam;
  const start = f.recorder.start({camera:true}); f.choose(); await start;
  assert.equal(draws,2); assert.equal(f.recorder.state,'recording');
  f.recorder.stop(); assert.equal(paused,2);
  assert.ok([...f.stream.getTracks(),...webcam.getTracks(),...canvasStream.getTracks()].every(t => t.stops === 1));
});
test('unsupported codecs and encoder errors release without fallback', async () => {
  const f = fixture(); f.recorder.Recorder = class { static isTypeSupported() { return false; } };
  const start = f.recorder.start(); f.choose(); await start;
  assert.equal(f.recorder.state,'idle'); assert.equal(f.stream.getTracks()[0].stops,1);
  const g = fixture(); const again = g.recorder.start(); g.choose(); await again;
  g.recorder.recorder.onerror(); assert.equal(g.saved.length,1); assert.equal(g.recorder.state,'idle');
});
