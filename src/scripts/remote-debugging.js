(function () {
    try {
        const { BrowserWindow } = require("electron");
        require("electron").BrowserWindow = (o) => {
            (o = o || {}).webPreferences = o.webPreferences || {};
            o.webPreferences.devTools = true;
            return new BrowserWindow(o);
        };
    } catch (e) {}
})();
