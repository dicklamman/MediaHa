const fs = require('fs');
let css = fs.readFileSync('home-assistant-addon/src/ui/styles.css', 'utf8');

const newStyles = \

/* MP3 Player Top Layout */
#mp3-top-layout {
    display: flex;
    flex-direction: row;
    gap: 20px;
    align-items: stretch;
    margin-bottom: 15px;
    height: 350px;
}

#mp3-cover {
    flex: 0 0 350px;
    max-width: 350px;
    width: 100%;
    object-fit: contain;
    display: none; /* Controlled by JS */
    border-radius: 8px;
    background: #000;
}

#mp3-lyrics {
    flex: 1;
    overflow-y: auto;
    padding: 15px;
    background: var(--info-bg, #1e1e1e);
    border-radius: 8px;
    text-align: center;
    font-size: 1.1em;
    line-height: 1.8;
    white-space: pre-wrap;
    box-sizing: border-box;
}

#mp3-lyrics.synced p {
    margin: 10px 0;
    transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
    opacity: 0.5;
    transform: scale(0.95);
    transform-origin: center;
}

#mp3-lyrics.synced p.active {
    opacity: 1;
    font-size: 1.5em;
    font-weight: 700;
    color: #00d8ff; /* Bright noticeable cyan */
    text-shadow: 0 0 10px rgba(0, 216, 255, 0.4);
    transform: scale(1.05); /* Make it bigger */
}

/* Mobile Responsiveness inner modifications */
\;

// Replace mobile responsivness inner styles
css = css.replace('  @media (max-width: 768px) {', newStyles + '  @media (max-width: 768px) {\n    #mp3-top-layout {\n        flex-direction: column;\n        align-items: center;\n        height: auto;\n    }\n    #mp3-cover {\n        flex: 0 0 auto;\n        max-width: 250px;\n        height: 250px;\n    }\n    #mp3-lyrics {\n        width: 100%;\n        height: 250px;\n    }\n');

fs.writeFileSync('home-assistant-addon/src/ui/styles.css', css, 'utf8');
