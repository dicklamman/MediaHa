with open('home-assistant-addon/src/ui/styles.css', 'r', encoding='utf-8') as f:
    css = f.read()

new_styles = '''

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
    border-radius: 8px;
    background: transparent;
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
    scroll-behavior: smooth;
}

#mp3-lyrics.synced p {
    margin: 10px 0;
    transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
    opacity: 0.5;
    transform: scale(0.95);
    transform-origin: center;
    cursor: pointer;
}

#mp3-lyrics.synced p.active {
    opacity: 1;
    font-size: 1.6em;
    font-weight: 700;
    color: #ff3366; /* Vibrant highlighted color */
    text-shadow: 0 0 12px rgba(255, 51, 102, 0.4);
    transform: scale(1.1);
}

'''

mobile_styles = '''  @media (max-width: 768px) {
    #mp3-top-layout {
        flex-direction: column;
        align-items: center;
        height: auto;
    }
    #mp3-cover {
        flex: 0 0 auto;
        max-width: 250px;
        height: 250px;
    }
    #mp3-lyrics {
        width: 100%;
        height: 250px;
    }
'''

css = css.replace('  @media (max-width: 768px) {', new_styles + mobile_styles)

with open('home-assistant-addon/src/ui/styles.css', 'w', encoding='utf-8') as f:
    f.write(css)
