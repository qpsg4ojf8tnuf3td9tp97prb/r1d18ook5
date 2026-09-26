const downloadIcon = `
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
                <g data-name="Layer 2"><g data-name="download">
                  <rect width="24" height="24" opacity="0"/>
                  <rect x="4" y="18" width="16" height="2" rx="1" ry="1"/>
                  <rect x="3" y="17" width="4" height="2" rx="1" ry="1" transform="rotate(-90 5 18)"/>
                  <rect x="17" y="17" width="4" height="2" rx="1" ry="1" transform="rotate(-90 19 18)"/>
                  <path d="M12 15a1 1 0 0 1-.58-.18l-4-2.82a1 1 0 0 1-.24-1.39 1 1 0 0 1 1.4-.24L12 12.76l3.4-2.56a1 1 0 0 1 1.2 1.6l-4 3a1 1 0 0 1-.6.2z"/>
                  <path d="M12 13a1 1 0 0 1-1-1V4a1 1 0 0 1 2 0v8a1 1 0 0 1-1 1z"/>
                </g></g>
              </svg>
            `;
function showPopup(message, type = "info", duration = 3000) {
    if (type === "error") {
        console.error(message);
    } else {
        console.log(message);
    }
    const popup = document.createElement("div");
    popup.textContent = message;
    popup.style.cssText = `
      position: fixed;
      top: 101px;
      right: 15px;
      padding: 10px 15px;
      background: white;
      border-left: 4px solid ${type === "error" ? "#ff4d4f" : "#1890ff"};
      border-radius: 4px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.15);
      z-index: 10000;
    `;

    document.body.appendChild(popup);

    if (duration > 0) {
        setTimeout(() => {
            if (popup.parentNode) {
                document.body.removeChild(popup);
            }
        }, duration);
    }

    return popup;
}

// resolve epub path
function resolvePath(baseDir, path) {
    if (path.startsWith("/")) return path.substring(1);
    if (!path.includes("../") && !path.includes("./")) return baseDir + path;

    const base = baseDir.split("/").filter(Boolean);
    const segments = path.split("/");
    const result = [...base];

    segments.forEach((segment) => {
        if (segment === "..") result.length && result.pop();
        else if (segment !== ".") result.push(segment);
    });

    return result.join("/");
}

function download(blob, filename) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
}

// fetch & download archive
async function getArchive(progress, baseUrl, pages, filename) {
    try {
        // Initialize file collection
        const files = new Map();

        // Common image file signatures (magic numbers)
        const imageSignatures = {
            ffd8ff: ".jpg", // JPEG
            "7b226a": ".jp2", // JPEG 2000
            "0000000c6a5020": ".jp2", // JPEG 2000 (another variation)
            "89504e47": ".png", // PNG
            "47494638": ".gif", // GIF
            "52494646": ".webp", // WEBP (starts with RIFF)
            "3026b275": ".webp", // WebP (another variation)
            "424d": ".bmp", // BMP
            "49492a00": ".tif", // TIFF (little endian)
            "4d4d002a": ".tif", // TIFF (big endian)
        };

        // Fetch pages
        progress.style.visibility = "visible";
        progress.max = pages;
        progress.value = 0;
        for (let i = 0; i <= pages; i++) {
            progress.value = i;
            const pageUrl = `${baseUrl}${i}`;
            const response = await fetch(pageUrl);
            const blob = await response.blob();

            // Read first 12 bytes of the file (to capture longer signatures)
            const buffer = await blob.slice(0, 12).arrayBuffer();
            const bytes = new Uint8Array(buffer);

            // Convert bytes to hex string
            let hex = "";
            for (let j = 0; j < bytes.length; j++) {
                hex += bytes[j].toString(16).padStart(2, "0");
            }

            // Check against known image signatures
            let isImage = false;
            let extension = ".bin";

            for (const signature in imageSignatures) {
                if (hex.startsWith(signature.toLowerCase())) {
                    extension = imageSignatures[signature];
                    isImage = true;
                    break;
                }
            }

            if (!isImage) {
                // throw new Error(`Error on page ${i}: Unsupported format. Only image formats are supported.`);
                showPopup(`Unknown format when ${i}`, "error");
            }

            files.set(`${i}${extension}`, blob);
        }
        progress.style.visibility = "hidden";

        // Pack to archive with maximum compression for all files
        const zip = new JSZip();
        files.forEach((blob, path) => {
            zip.file(path, blob, {
                compression: "DEFLATE",
                compressionOptions: { level: 9 },
            });
        });

        showPopup("Start archiving...");
        download(await zip.generateAsync({ type: "blob" }), `${filename}.zip`);
        showPopup("Archived successfully!");
    } catch (error) {
        showPopup(`Error creating archive: ${error.message}`, "error");
    }
}

// fetch & download epub
async function getEpub(progress, baseUrl, filename) {
    try {
        // initialize file collection
        const files = new Map();
        files.set(
            "mimetype",
            new Blob(["application/epub+zip"], { type: "text/plain" })
        );

        progress.max = 3;
        progress.value = 0;
        progress.style.visibility = "visible";

        // fetch & resolve container.xml, then get opf path
        const containerRes = await fetch(`${baseUrl}META-INF/container.xml`);
        files.set("META-INF/container.xml", await containerRes.clone().blob());
        const containerXml = new DOMParser().parseFromString(
            await containerRes.text(),
            "application/xml"
        );
        const opfPath = containerXml
            .querySelector("rootfile")
            .getAttribute("full-path");

        progress.value = 1;

        // fetch & resolve opf, then get file list
        const opfUrl = new URL(opfPath, baseUrl).href;
        const opfRes = await fetch(opfUrl);
        files.set(opfPath, await opfRes.clone().blob());
        const opfXml = new DOMParser().parseFromString(
            await opfRes.text(),
            "application/xml"
        );
        const opfDir = opfPath.includes("/")
            ? opfPath.substring(0, opfPath.lastIndexOf("/") + 1)
            : "";
        const items = [...opfXml.querySelectorAll("manifest > item")];

        progress.max = 2 + items.length;
        progress.value = 2;

        let currentFile = 0;
        await Promise.all(
            items.map(async (item) => {
                const href = item.getAttribute("href");
                const url = new URL(href, opfUrl).href;
                const path = resolvePath(opfDir, decodeURIComponent(href));

                const res = await fetch(url);
                files.set(path, await res.blob());

                currentFile++;
                progress.value = 2 + currentFile;
            })
        );

        progress.style.visibility = "hidden";

        // pack to epub
        const zip = new JSZip();
        files.forEach((blob, path) => {
            zip.file(
                path,
                blob,
                path === "mimetype"
                    ? { compression: "STORE" }
                    : {
                          compression: "DEFLATE",
                          compressionOptions: { level: 9 },
                      }
            );
        });

        showPopup("Start packing...");
        download(await zip.generateAsync({ type: "blob" }), `${filename}.epub`);
        showPopup("Packed successfully!");
    } catch (error) {
        showPopup(`Error creating EPUB: ${error.message}`, "error");
    }
}

// Helper function to wait for DOM element with timeout
function waitFor(selector, timeout = 5000) {
    return new Promise((resolve, reject) => {
        // Check if element already exists
        const element = document.querySelector(selector);
        if (element) return resolve(element);

        // Set timeout to avoid infinite waiting
        const timer = setTimeout(() => {
            observer.disconnect();
            reject(
                new Error(
                    `Timeout waiting for element with selector "${selector}"`
                )
            );
        }, timeout);

        // Watch for DOM changes
        const observer = new MutationObserver(() => {
            const element = document.querySelector(selector);
            if (element) {
                observer.disconnect();
                clearTimeout(timer);
                resolve(element);
            }
        });
        observer.observe(document.body, { childList: true, subtree: true });
    });
}

async function isNovelPage() {
    try {
        await waitFor("ridi-page-view", 2000);
        return true;
    } catch {
        return false;
    }
}

async function isComicPage() {
    try {
        await waitFor("input[type='range']", 2000);
        const hasComicImage =
            !!document.querySelector("img.page-right") ||
            !!document.querySelector("img.page-left");
        return hasComicImage;
    } catch {
        return false;
    }
}

async function init() {
    try {
        // Wait for DOM if needed
        if (document.readyState === "loading") {
            await new Promise((resolve) =>
                document.addEventListener("DOMContentLoaded", resolve)
            );
        }

        // Determine page type (novel or comic)
        const isNovel = await isNovelPage().catch(() => false);
        const isComic = !isNovel && (await isComicPage().catch(() => false));

        if (!isNovel && !isComic) {
            return showPopup("This page is not supported", "error");
        }
        const pages = isComic
            ? +document.querySelector("input[type='range']").max + 1
            : 0;

        // Find UI elements
        const title = document.querySelector("div[title]");
        const btnArea =
            title?.parentElement?.parentElement?.parentElement?.querySelectorAll(
                ":scope > div"
            )?.[1];
        if (!btnArea) return showPopup("UI elements not found", "error");

        // Create download button
        const btn = btnArea.querySelector(":scope > button").cloneNode(true);
        btn.childNodes[btn.childNodes.length - 1].nodeValue = "Download";

        // Add progress bar
        const progress = document.createElement("progress");
        progress.style.visibility = "hidden";
        btn.appendChild(progress);

        // Set icon
        const icon = btn.querySelector(":scope > div");
        if (icon) {
            icon.removeAttribute("style");
            icon.style.background = "transparent";
            icon.innerHTML = downloadIcon;
        }

        // Set click handler based on page type
        btn.addEventListener("click", () => {
            if (isNovel) {
                const rawUrl = ((u) =>
                    u.origin + "/" + u.pathname.split("/")[1])(
                    new URL(location.href)
                );
                if (!rawUrl || !rawUrl.endsWith("-file")) {
                    showPopup(
                        `Error: Error resolving base URL. Please check the page at "${location.href}".`,
                        "error",
                        5000
                    );
                    return;
                }
                const baseUrl = rawUrl.slice(0, -5) + "-entry/";
                if (baseUrl)
                    getEpub(
                        progress,
                        baseUrl,
                        title.getAttribute("title") || "novel"
                    );
            } else {
                const imgEl =
                    document.querySelector("img.page-right") ||
                    document.querySelector("img.page-left");
                if (imgEl) {
                    const baseUrl = `${imgEl.src.split("-page")[0]}-page/`;
                    getArchive(
                        progress,
                        baseUrl,
                        pages,
                        title.getAttribute("title") || "comic"
                    );
                }
            }
        });

        // Add button to UI when content is loaded
        const addButton = () => btnArea.appendChild(btn);
        document.readyState === "complete"
            ? addButton()
            : window.addEventListener("load", addButton);
    } catch (error) {
        showPopup(`Initialization error: ${error.message}`, "error");
    }
}

(async () => init())();
