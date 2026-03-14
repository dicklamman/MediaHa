const fs = require("fs");
const fPath = "home-assistant-addon/src/ui/js/mp3Player.js";
let js = fs.readFileSync(fPath, "utf8");

// Add revert logic in loadMetadata and generic listeners
js = js.replace(
`const metadata = await this.api.getMetadata(this.currentFile.path);`,
`const metadata = await this.api.getMetadata(this.currentFile.path);\n            this.originalMetadata = metadata; // Keep original\n            document.querySelectorAll(".revert-btn").forEach(btn => btn.style.display = "none");`
);

// In autoEnhance, show revert buttons
js = js.replace(
`// Populate form with fetched data
            if (data.title) document.getElementById('meta-input-title').value = data.title;
            if (data.artist) document.getElementById('meta-input-artist').value = data.artist;
            if (data.album) document.getElementById('meta-input-album').value = data.album;
            if (data.lyrics) document.getElementById('meta-input-lyrics').value = data.lyrics;`,
`// Populate form with fetched data
            if (data.title) {
                document.getElementById('meta-input-title').value = data.title;
                document.querySelector('.revert-btn[data-field="title"]').style.display = "inline-block";
            }
            if (data.artist) {
                document.getElementById('meta-input-artist').value = data.artist;
                document.querySelector('.revert-btn[data-field="artist"]').style.display = "inline-block";
            }
            if (data.album) {
                document.getElementById('meta-input-album').value = data.album;
                document.querySelector('.revert-btn[data-field="album"]').style.display = "inline-block";
            }
            if (data.lyrics) {
                document.getElementById('meta-input-lyrics').value = data.lyrics;
                document.querySelector('.revert-btn[data-field="lyrics"]').style.display = "inline-block";
            }`
);

// In autoEnhance for cover
js = js.replace(
`// Preview image
            if (data.cover) {
                this.pendingCover = data.cover;`,
`// Preview image
            if (data.cover) {
                this.pendingCover = data.cover;
                document.querySelector('.revert-btn[data-field="cover"]').style.display = "inline-block";`
);

// And we need to attach event listeners to revert buttons inside init()
if (!js.includes("revert-btn")) {
    js = js.replace(
        `const autoBtn = document.getElementById('auto-enhance-btn');`,
        `const autoBtn = document.getElementById('auto-enhance-btn');

        // Revert buttons for metadata fields
        document.querySelectorAll(".revert-btn").forEach(btn => {
            btn.addEventListener("click", (e) => {
                e.preventDefault();
                const field = btn.getAttribute("data-field");
                if (!this.originalMetadata) return;

                if (field === "cover") {
                    this.pendingCover = null;
                    const mp3Cover = document.getElementById("mp3-cover");
                    if (this.originalMetadata.cover) {
                        mp3Cover.src = this.originalMetadata.cover;
                        mp3Cover.style.display = "block";
                    } else {
                        if (mp3Cover) mp3Cover.style.display = "none";
                    }
                } else if (field === "lyrics") {
                    document.getElementById("meta-input-lyrics").value = this.originalMetadata.lyrics || "";
                } else {
                    document.getElementById("meta-input-" + field).value = this.originalMetadata[field] || "";
                }
                btn.style.display = "none";
            });
        });`
    );
}

fs.writeFileSync(fPath, js);
