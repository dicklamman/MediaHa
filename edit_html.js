const fs = require("fs");
const fPath = "home-assistant-addon/src/ui/index.html";
let html = fs.readFileSync(fPath, "utf8");

html = html.replace(
`<label style="display:block; font-weight:bold; margin-bottom: 5px;">Title</label>`,
`<label style="display:flex; justify-content:space-between; font-weight:bold; margin-bottom: 5px;">Title <button class="btn btn-small revert-btn" data-field="title" style="display:none; padding:2px 8px; font-size: 0.8em; background:#6c757d;">Revert to Existing</button></label>`
);

html = html.replace(
`<label style="display:block; font-weight:bold; margin-bottom: 5px;">Artist</label>`,
`<label style="display:flex; justify-content:space-between; font-weight:bold; margin-bottom: 5px;">Artist <button class="btn btn-small revert-btn" data-field="artist" style="display:none; padding:2px 8px; font-size: 0.8em; background:#6c757d;">Revert to Existing</button></label>`
);

html = html.replace(
`<label style="display:block; font-weight:bold; margin-bottom: 5px;">Album</label>`,
`<label style="display:flex; justify-content:space-between; font-weight:bold; margin-bottom: 5px;">Album <button class="btn btn-small revert-btn" data-field="album" style="display:none; padding:2px 8px; font-size: 0.8em; background:#6c757d;">Revert to Existing</button></label>`
);

html = html.replace(
`<label style="display:block; font-weight:bold; margin-bottom: 5px;">Lyrics (.lrc file)</label>`,
`<label style="display:flex; justify-content:space-between; font-weight:bold; margin-bottom: 5px;">Lyrics (.lrc) <button class="btn btn-small revert-btn" data-field="lyrics" style="display:none; padding:2px 8px; font-size: 0.8em; background:#6c757d;">Revert to Existing</button></label>`
);

if (!html.includes('data-field="cover"')) {
    html = html.replace(
        `</div>\n                </div>\n            </div>`,
        `</div>
                    <div style="margin-bottom: 10px; display:flex; justify-content:space-between; font-weight:bold;">
                        Cover Image <button class="btn btn-small revert-btn" data-field="cover" style="display:none; padding:2px 8px; font-size: 0.8em; background:#6c757d;">Revert to Existing</button>
                    </div>
                </div>
            </div>`
    );
}

fs.writeFileSync(fPath, html);
