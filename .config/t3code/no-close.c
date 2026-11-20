/* Electron reads its Linux caption buttons and native menu colours from GTK.
 * Keep both local to T3, including when an editor or browser inherits
 * GTK_MODULES from it. Forward declarations avoid requiring the GTK
 * development packages. */
#include <string.h>
#include <unistd.h>

typedef struct _GtkSettings GtkSettings;
typedef struct _GtkCssProvider GtkCssProvider;
typedef struct _GdkScreen GdkScreen;
extern GtkSettings *gtk_settings_get_default(void);
extern GtkCssProvider *gtk_css_provider_new(void);
extern int gtk_css_provider_load_from_data(GtkCssProvider *, const char *, long, void **);
extern GdkScreen *gdk_screen_get_default(void);
extern void gtk_style_context_add_provider_for_screen(GdkScreen *, void *, unsigned int);
extern void g_object_set(void *, const char *, ...);

/* Tokyo Drift colours for Electron's thread and project context menus.
 * Chromium samples these GTK nodes once and only uses their colours, so blur,
 * radius and padding have no effect here. */
static const char menu_css[] =
    "menu, .menu, .context-menu {"
    "  background-color: #1f2336; color: #c8d3f5; border: 1px solid #414868; }"
    "menu menuitem { color: #c8d3f5; }"
    "menu menuitem:hover { background-color: #7aa2f7; color: #1a1b26; }"
    "menu menuitem:hover label, menu menuitem:hover accelerator { color: #1a1b26; }"
    "menu menuitem accelerator { color: #a9b1d6; }"
    "menu menuitem:disabled, menu menuitem:disabled label { color: #565f89; }"
    "menu separator { background-color: #32333e; color: #32333e; }";

/* Above the user's theme (800 is GTK_STYLE_PROVIDER_PRIORITY_USER). */
#define MENU_STYLE_PRIORITY 800

static void style_menus(void) {
    GdkScreen *screen = gdk_screen_get_default();
    if (!screen) return;
    GtkCssProvider *provider = gtk_css_provider_new();
    if (gtk_css_provider_load_from_data(provider, menu_css, -1, 0))
        gtk_style_context_add_provider_for_screen(screen, provider, MENU_STYLE_PRIORITY);
}

void gtk_module_init(int *argc, char ***argv) {
    (void)argc;
    (void)argv;
    char executable[4096];
    ssize_t length = readlink("/proc/self/exe", executable, sizeof(executable) - 1);
    if (length < 0) return;
    executable[length] = '\0';
    const char *name = strrchr(executable, '/');
    if (!name || strcmp(name + 1, "t3code") != 0) return;
    g_object_set(gtk_settings_get_default(), "gtk-decoration-layout", ":", (void *)0);
    style_menus();
}
