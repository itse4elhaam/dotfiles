/* Electron reads its Linux caption buttons from GtkSettings. Keep this local
 * to T3, including when an editor or browser inherits GTK_MODULES from it.
 * Forward declarations avoid requiring the GTK development packages. */
#include <string.h>
#include <unistd.h>

typedef struct _GtkSettings GtkSettings;
extern GtkSettings *gtk_settings_get_default(void);
extern void g_object_set(void *, const char *, ...);

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
}
