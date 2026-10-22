/* No network, content scripts, native messaging, or capture on page load. */
class TabRecorder {
  constructor(api, media, Recorder, notify, saved) {
    this.api = api; this.media = media; this.Recorder = Recorder;
    this.notify = notify; this.saved = saved;
    this.generation = 0; this.streams = []; this.state = 'idle';
  }
  own(stream, generation) {
    if (generation !== this.generation) {
      stream.getTracks().forEach(track => track.stop());
      throw new Error('Recording cancelled.');
    }
    this.streams.push(stream);
    stream.getTracks().forEach(track => track.addEventListener('ended', () => this.stop(), {once:true}));
    return stream;
  }
  release() {
    cancelAnimationFrame(this.frame || 0);
    this.streams.splice(0).forEach(stream => stream.getTracks().forEach(track => track.stop()));
    if (this.context) { this.context.close(); this.context = null; }
    (this.videos || []).forEach(video => { video.pause(); video.srcObject = null; });
    this.videos = [];
  }
  async start({audio = false, mic = false, camera = false} = {}) {
    if (this.state !== 'idle') return;
    const generation = ++this.generation;
    this.state = 'choosing'; this.notify('Choose a tab. Cancel captures nothing.');
    try {
      const choice = await new Promise(resolve => {
        this.request = this.api.chooseDesktopMedia(audio ? ['tab','audio'] : ['tab'],
          (id, options) => { this.request = null; resolve({id, options}); });
      });
      if (generation !== this.generation) return;
      if (!choice.id) throw new Error('Tab selection cancelled.');
      const constraints = {mandatory:{chromeMediaSource:'desktop', chromeMediaSourceId:choice.id}};
      const tab = this.own(await this.media.getUserMedia({video:constraints,
        audio:audio && choice.options?.canRequestAudioTrack ? constraints : false}), generation);
      if (!tab.getVideoTracks().length || tab.getVideoTracks()[0].readyState === 'ended')
        throw new Error('The chosen tab supplied no live video.');
      if (audio && choice.options?.canRequestAudioTrack && !tab.getAudioTracks().length)
        throw new Error('Shared tab audio is unavailable. Retry without tab audio.');
      let output = tab;
      let microphone;
      if (mic) {
        microphone = this.own(await this.media.getUserMedia({audio:true, video:false}), generation);
        if (!microphone.getAudioTracks().length) throw new Error('Microphone supplied no audio.');
      }
      if (camera) {
        const webcam = this.own(await this.media.getUserMedia({video:true, audio:false}), generation);
        if (!webcam.getVideoTracks().length) throw new Error('Camera supplied no video.');
        output = await this.compose(tab, webcam, generation);
      }
      if (mic) {
        this.context = new AudioContext();
        await this.context.resume();
        if (generation !== this.generation) throw new Error('Recording cancelled.');
        const destination = this.context.createMediaStreamDestination();
        for (const stream of [tab, microphone]) {
          if (stream.getAudioTracks().length) this.context.createMediaStreamSource(stream).connect(destination);
        }
        this.own(destination.stream, generation);
        output = new MediaStream([...output.getVideoTracks(), ...destination.stream.getAudioTracks()]);
      } else if (camera) {
        output = new MediaStream([...output.getVideoTracks(), ...tab.getAudioTracks()]);
      }
      if (generation !== this.generation || tab.getVideoTracks()[0].readyState === 'ended')
        throw new Error('The selected tab is no longer available.');
      const codec = ['video/webm;codecs=vp9,opus','video/webm;codecs=vp8,opus','video/webm']
        .find(type => this.Recorder.isTypeSupported(type));
      if (!codec) throw new Error('This browser cannot record WebM.');
      const recorder = this.recorder = new this.Recorder(output, {mimeType:codec});
      const chunks = [];
      recorder.ondataavailable = event => { if (event.data.size) chunks.push(event.data); };
      recorder.onstop = () => {
        this.release(); this.recorder = null; this.state = 'idle';
        const blob = new Blob(chunks, {type:codec});
        if (blob.size) this.saved(blob);
        this.notify(blob.size ? 'Stopped. Download your recording before closing this page.' : 'Stopped. No video data was produced.');
      };
      recorder.onerror = () => { this.notify('Browser encoder failed. Saving available data.'); this.stop(); };
      recorder.start(1000); this.state = 'recording';
      this.notify(audio && !choice.options?.canRequestAudioTrack ? 'Recording tab. Tab audio was not shared.' : 'Recording the selected tab.');
    } catch (error) {
      if (generation !== this.generation) return;
      this.stop(); this.notify(error.message || 'Browser permission was denied.');
    }
  }
  async compose(tab, webcam, generation) {
    const videos = this.videos = [tab, webcam].map(stream => {
      const video = document.createElement('video'); video.srcObject = stream; video.muted = true; return video;
    });
    await Promise.all(videos.map(video => video.play()));
    if (generation !== this.generation) throw new Error('Recording cancelled.');
    const canvas = document.createElement('canvas');
    canvas.width = videos[0].videoWidth; canvas.height = videos[0].videoHeight;
    if (!canvas.width || !canvas.height) throw new Error('The tab supplied no image dimensions.');
    const ctx = canvas.getContext('2d');
    const draw = () => {
      ctx.drawImage(videos[0], 0, 0, canvas.width, canvas.height);
      const size = Math.min(canvas.width, canvas.height) * .22, margin = size * .12;
      ctx.save(); ctx.beginPath();
      ctx.arc(canvas.width-size/2-margin, canvas.height-size/2-margin, size/2, 0, Math.PI*2); ctx.clip();
      ctx.drawImage(videos[1], canvas.width-size-margin, canvas.height-size-margin, size, size); ctx.restore();
      this.frame = requestAnimationFrame(draw);
    };
    draw(); return this.own(canvas.captureStream(30), generation);
  }
  stop() {
    ++this.generation;
    if (this.request != null) { this.api.cancelChooseDesktopMedia(this.request); this.request = null; }
    if (this.recorder && this.recorder.state !== 'inactive') {
      this.state = 'saving'; this.recorder.stop(); this.release();
    } else if (this.state !== 'saving') {
      this.release(); this.state = 'idle'; this.notify('Cancelled. Capture released.');
    }
  }
}
