const fs = require("fs");
const fPath = "home-assistant-addon/src/ui/styles.css";
let css = fs.readFileSync(fPath, "utf8");

if (!css.includes("::-webkit-scrollbar")) {
    css += `
/* Custom elegant scrollbar for lyrics */
#mp3-lyrics::-webkit-scrollbar {
    width: 6px;
}
#mp3-lyrics::-webkit-scrollbar-track {
    background: transparent; 
}
#mp3-lyrics::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.2); 
    border-radius: 10px;
}
#mp3-lyrics::-webkit-scrollbar-thumb:hover {
    background: rgba(255, 255, 255, 0.4); 
}
`;
}

fs.writeFileSync(fPath, css);
