(() => {
    const electron = require("electron");
    const OriginalBW = electron.BrowserWindow;
    if (OriginalBW.__ridi_patched__) return;

    class PatchedBW extends OriginalBW {
        constructor(opts = {}) {
            opts.webPreferences = { ...opts.webPreferences, devTools: true };
            super(opts);
        }
    }
    Object.setPrototypeOf(PatchedBW, OriginalBW);
    OriginalBW.__ridi_patched__ = true;
    electron.BrowserWindow = PatchedBW;
})();
