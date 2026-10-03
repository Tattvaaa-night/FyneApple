(function () {
    "use strict";


    const forms =
        document.querySelectorAll(
            'form[action="/search"]'
        );


    let suggestionController =
        null;


    const RECENT_STORAGE_KEY =
        "fyneapple_recent_searches";


    /*
     * ---------------------------------------------------------
     * Utility
     * ---------------------------------------------------------
     */


    function escapeHtml(value) {

        const element =
            document.createElement(
                "div"
            );


        element.textContent =
            value;


        return element.innerHTML;
    }


    function getSuggestionBox(form) {

        return form.querySelector(
            ".fyne-suggestions"
        );

    }


    function closeSuggestions(form) {

        const box =
            getSuggestionBox(
                form
            );


        if (!box) {
            return;
        }


        box.classList.add(
            "hidden"
        );


        box.innerHTML =
            "";

    }


    /*
     * ---------------------------------------------------------
     * Recent Searches
     * ---------------------------------------------------------
     */


    function getRecentSearches() {

        try {

            const stored =
                localStorage.getItem(
                    RECENT_STORAGE_KEY
                );


            if (!stored) {

                return [];

            }


            const parsed =
                JSON.parse(
                    stored
                );


            if (
                !Array.isArray(
                    parsed
                )
            ) {

                return [];

            }


            return parsed
                .filter(
                    item =>
                        typeof item ===
                        "string"
                )
                .map(
                    item =>
                        item.trim()
                )
                .filter(
                    item =>
                        item.length > 0
                )
                .slice(
                    0,
                    8
                );

        } catch {

            return [];

        }

    }


    function saveRecentSearch(
        query
    ) {

        const cleaned =
            query.trim();


        if (!cleaned) {

            return;

        }


        const current =
            getRecentSearches();


        const filtered =
            current.filter(
                item =>
                    item.toLowerCase()
                    !==
                    cleaned.toLowerCase()
            );


        const updated = [

            cleaned,

            ...filtered,

        ].slice(
            0,
            8
        );


        localStorage.setItem(
            RECENT_STORAGE_KEY,
            JSON.stringify(
                updated
            )
        );

    }


    function removeRecentSearch(
        query,
        form
    ) {

        const updated =
            getRecentSearches()
                .filter(
                    item =>
                        item.toLowerCase()
                        !==
                        query.toLowerCase()
                );


        localStorage.setItem(
            RECENT_STORAGE_KEY,
            JSON.stringify(
                updated
            )
        );


        showRecentSuggestions(
            form
        );

    }


    function clearAllRecentSearches(
        form
    ) {

        localStorage.removeItem(
            RECENT_STORAGE_KEY
        );


        closeSuggestions(
            form
        );

    }


    /*
     * ---------------------------------------------------------
     * Suggestion Components
     * ---------------------------------------------------------
     */


    function createLiveSuggestion(
        text,
        form
    ) {

        const button =
            document.createElement(
                "button"
            );


        button.type =
            "button";


        button.className =
            "fyne-suggestion-item";


        button.innerHTML = `

            <span
                class="fyne-suggestion-icon"
            >
                ⌕
            </span>

            <span
                class="fyne-suggestion-text"
            >
                ${escapeHtml(text)}
            </span>

            <span
                class="fyne-suggestion-arrow"
            >
                ↗
            </span>

        `;


        button.addEventListener(
            "click",
            () => {

                const input =
                    form.querySelector(
                        'input[name="q"]'
                    );


                if (!input) {
                    return;
                }


                input.value =
                    text;


                saveRecentSearch(
                    text
                );


                closeSuggestions(
                    form
                );


                form.submit();

            }
        );


        return button;

    }


    function createRecentSuggestion(
        text,
        form
    ) {

        const wrapper =
            document.createElement(
                "div"
            );


        wrapper.className =
            "fyne-recent-item";


        wrapper.innerHTML = `

            <button
                type="button"
                class="fyne-recent-main"
            >

                <span
                    class="fyne-suggestion-icon"
                >
                    ↺
                </span>

                <span
                    class="fyne-suggestion-text"
                >
                    ${escapeHtml(text)}
                </span>

            </button>


            <button
                type="button"
                class="fyne-recent-delete"
                aria-label="Delete recent search: ${escapeHtml(text)}"
                title="Delete this recent search"
            >
                ×
            </button>

        `;


        const mainButton =
            wrapper.querySelector(
                ".fyne-recent-main"
            );


        const deleteButton =
            wrapper.querySelector(
                ".fyne-recent-delete"
            );


        mainButton.addEventListener(
            "click",
            () => {

                const input =
                    form.querySelector(
                        'input[name="q"]'
                    );


                if (!input) {
                    return;
                }


                input.value =
                    text;


                closeSuggestions(
                    form
                );


                form.submit();

            }
        );


        deleteButton.addEventListener(
            "click",
            event => {

                event.preventDefault();

                event.stopPropagation();


                removeRecentSearch(
                    text,
                    form
                );

            }
        );


        return wrapper;

    }


    function createClearAllButton(
        form
    ) {

        const button =
            document.createElement(
                "button"
            );


        button.type =
            "button";


        button.className =
            "fyne-clear-all";


        button.innerHTML = `

            <span>
                Clear all
            </span>

            <span>
                ×
            </span>

        `;


        button.addEventListener(
            "click",
            event => {

                event.preventDefault();

                event.stopPropagation();


                clearAllRecentSearches(
                    form
                );

            }
        );


        return button;

    }


    function showRecentSuggestions(
        form
    ) {

        const box =
            getSuggestionBox(
                form
            );


        if (!box) {
            return;
        }


        const recent =
            getRecentSearches();


        if (!recent.length) {

            closeSuggestions(
                form
            );

            return;

        }


        box.innerHTML =
            "";


        const header =
            document.createElement(
                "div"
            );


        header.className =
            "fyne-suggestion-header";


        header.innerHTML = `

            <span>
                Recent searches
            </span>

        `;


        box.appendChild(
            header
        );


        recent.forEach(
            search => {

                box.appendChild(
                    createRecentSuggestion(
                        search,
                        form
                    )
                );

            }
        );


        box.appendChild(
            createClearAllButton(
                form
            )
        );


        box.classList.remove(
            "hidden"
        );

    }


    function renderLiveSuggestions(
        form,
        values
    ) {

        const box =
            getSuggestionBox(
                form
            );


        if (!box) {
            return;
        }


        const unique =
            [];


        const seen =
            new Set();


        values.forEach(
            value => {

                const text =
                    String(
                        value
                    ).trim();


                if (!text) {
                    return;
                }


                const key =
                    text.toLowerCase();


                if (
                    seen.has(key)
                ) {
                    return;
                }


                seen.add(
                    key
                );


                unique.push(
                    text
                );

            }
        );


        if (!unique.length) {

            closeSuggestions(
                form
            );

            return;

        }


        box.innerHTML =
            "";


        const header =
            document.createElement(
                "div"
            );


        header.className =
            "fyne-suggestion-header";


        header.innerHTML = `

            <span>
                FyneApple suggestions
            </span>

        `;


        box.appendChild(
            header
        );


        unique
            .slice(
                0,
                6
            )
            .forEach(
                suggestion => {

                    box.appendChild(
                        createLiveSuggestion(
                            suggestion,
                            form
                        )
                    );

                }
            );


        box.classList.remove(
            "hidden"
        );

    }


    /*
     * ---------------------------------------------------------
     * Live Suggestions API
     * ---------------------------------------------------------
     */


    async function fetchSuggestions(
        query,
        form
    ) {

        const trimmed =
            query.trim();


        if (
            trimmed.length < 2
        ) {

            showRecentSuggestions(
                form
            );

            return;

        }


        if (
            suggestionController
        ) {

            suggestionController.abort();

        }


        suggestionController =
            new AbortController();


        try {

            const response =
                await fetch(
                    `/api/suggestions?q=${encodeURIComponent(trimmed)}`,
                    {
                        signal:
                            suggestionController.signal
                    }
                );


            if (
                !response.ok
            ) {

                throw new Error(
                    "Suggestion request failed."
                );

            }


            const suggestions =
                await response.json();


            renderLiveSuggestions(
                form,
                suggestions.map(
                    item =>
                        item.text
                )
            );


        } catch (error) {

            if (
                error.name ===
                "AbortError"
            ) {

                return;

            }


            showRecentSuggestions(
                form
            );

        }

    }


    /*
     * ---------------------------------------------------------
     * Search Forms
     * ---------------------------------------------------------
     */


    forms.forEach(
        form => {

            const input =
                form.querySelector(
                    'input[name="q"]'
                );


            if (!input) {
                return;
            }


            let suggestionTimer =
                null;


            input.addEventListener(
                "input",
                () => {

                    clearTimeout(
                        suggestionTimer
                    );


                    suggestionTimer =
                        setTimeout(
                            () => {

                                fetchSuggestions(
                                    input.value,
                                    form
                                );

                            },
                            380
                        );

                }
            );


            input.addEventListener(
                "focus",
                () => {

                    if (
                        input.value.trim()
                            .length >= 2
                    ) {

                        fetchSuggestions(
                            input.value,
                            form
                        );

                    } else {

                        showRecentSuggestions(
                            form
                        );

                    }

                }
            );


            form.addEventListener(
                "submit",
                () => {

                    saveRecentSearch(
                        input.value
                    );


                    closeSuggestions(
                        form
                    );

                }
            );


            document.addEventListener(
                "click",
                event => {

                    if (
                        !form.contains(
                            event.target
                        )
                    ) {

                        closeSuggestions(
                            form
                        );

                    }

                }
            );

        }
    );


    /*
     * ---------------------------------------------------------
     * Topic Chips
     * ---------------------------------------------------------
     */


    document
        .querySelectorAll(
            ".topic-chip"
        )
        .forEach(
            chip => {

                chip.addEventListener(
                    "click",
                    () => {

                        const main =
                            chip.closest(
                                "main"
                            );


                        const form =
                            main?.querySelector(
                                'form[action="/search"]'
                            );


                        if (!form) {
                            return;
                        }


                        const input =
                            form.querySelector(
                                'input[name="q"]'
                            );


                        if (!input) {
                            return;
                        }


                        input.value =
                            chip.dataset.query ||
                            "";


                        form.submit();

                    }
                );

            }
        );


    /*
     * ---------------------------------------------------------
     * I'm Feeling Curious
     * ---------------------------------------------------------
     */


    const curiousButton =
        document.getElementById(
            "curious-button"
        );


    if (
        curiousButton
    ) {

        const curiousQueries = [

            "how did the internet start",

            "how do neural networks work",

            "how does GPS work",

            "history of smartphones",

            "what is quantum computing",

            "why is the sky blue",

            "best programming languages to learn",

            "Cristiano Ronaldo",

            "how to learn DSA",

            "best places to visit in India",

            "easy high protein recipes"

        ];


        curiousButton.addEventListener(
            "click",
            () => {

                const index =
                    Math.floor(
                        Math.random()
                        *
                        curiousQueries.length
                    );


                const selected =
                    curiousQueries[
                        index
                    ];


                const form =
                    document.getElementById(
                        "search-form"
                    );


                const input =
                    document.getElementById(
                        "query"
                    );


                if (
                    form &&
                    input
                ) {

                    input.value =
                        selected;


                    form.submit();

                }

            }
        );

    }


    /*
     * ---------------------------------------------------------
     * Keyboard Shortcut
     * ---------------------------------------------------------
     */


    document.addEventListener(
        "keydown",
        event => {

            const active =
                document.activeElement;


            if (
                event.key === "/" &&
                active &&
                ![
                    "INPUT",
                    "TEXTAREA",
                    "SELECT"
                ].includes(
                    active.tagName
                )
            ) {

                const input =
                    document.querySelector(
                        'input[name="q"]'
                    );


                if (!input) {
                    return;
                }


                event.preventDefault();


                input.focus();

                input.select();

            }


            if (
                event.key === "Escape"
            ) {

                document.querySelectorAll(
                    ".fyne-suggestions"
                ).forEach(
                    box => {

                        box.classList.add(
                            "hidden"
                        );

                    }
                );

            }

        }
    );


    /*
     * ---------------------------------------------------------
     * Focus Button
     * ---------------------------------------------------------
     */


    const focusButton =
        document.getElementById(
            "focus-button"
        );


    if (
        focusButton
    ) {

        focusButton.addEventListener(
            "click",
            () => {

                const input =
                    document.querySelector(
                        'input[name="q"]'
                    );


                if (input) {

                    input.focus();

                    input.select();

                }

            }
        );

    }


    /*
     * ---------------------------------------------------------
     * Mouse Glow
     * ---------------------------------------------------------
     */


    const cursorGlow =
        document.getElementById(
            "cursor-glow"
        );


    if (
        cursorGlow
    ) {

        document.addEventListener(
            "mousemove",
            event => {

                cursorGlow.style.left =
                    `${event.clientX}px`;

                cursorGlow.style.top =
                    `${event.clientY}px`;

            }
        );

    }


    /*
     * ---------------------------------------------------------
     * Voice Search
     * ---------------------------------------------------------
     */


    const voiceButton =
        document.getElementById(
            "voice-button"
        );


    const mainForm =
        document.getElementById(
            "search-form"
        );


    const mainQuery =
        document.getElementById(
            "query"
        );


    const SpeechRecognition =
        window.SpeechRecognition ||
        window.webkitSpeechRecognition;


    if (
        voiceButton &&
        mainForm &&
        mainQuery &&
        SpeechRecognition
    ) {

        const recognition =
            new SpeechRecognition();


        recognition.lang =
            "en-IN";


        recognition.interimResults =
            false;


        recognition.maxAlternatives =
            1;


        voiceButton.addEventListener(
            "click",
            () => {

                try {

                    recognition.start();

                } catch (error) {

                    console.warn(
                        "Voice search could not start.",
                        error
                    );

                }

            }
        );


        recognition.addEventListener(
            "result",
            event => {

                const transcript =
                    event.results[0][0]
                        .transcript
                        .trim();


                if (!transcript) {
                    return;
                }


                mainQuery.value =
                    transcript;


                mainForm.submit();

            }
        );

    }


    /*
     * ---------------------------------------------------------
     * Rufus Music Player
     * ---------------------------------------------------------
     */


    const musicButton =
        document.getElementById(
            "rufus-button"
        );


    const musicLabel =
        document.getElementById(
            "rufus-label"
        );


    const visualizer =
        document.getElementById(
            "rufus-visualizer"
        );


    const musicVolume =
        document.getElementById(
            "rufus-volume"
        );


    let audioContext =
        null;


    let masterGain =
        null;


    let musicTimer =
        null;


    let musicPlaying =
        false;


    let musicStep =
        0;


    const melody = [

        261.63,

        293.66,

        392.00,

        329.63,

        440.00,

        392.00,

        329.63,

        293.66

    ];


    function initializeAudio() {

        if (audioContext) {

            return;

        }


        const AudioContext =
            window.AudioContext ||
            window.webkitAudioContext;


        if (!AudioContext) {

            return;

        }


        audioContext =
            new AudioContext();


        masterGain =
            audioContext.createGain();


        masterGain.gain.value =
            0.045;


        masterGain.connect(
            audioContext.destination
        );

    }


    function playNote(
        frequency
    ) {

        if (
            !audioContext ||
            !masterGain
        ) {

            return;

        }


        const now =
            audioContext.currentTime;


        const oscillator =
            audioContext.createOscillator();


        const envelope =
            audioContext.createGain();


        oscillator.type =
            "sine";


        oscillator.frequency.setValueAtTime(
            frequency,
            now
        );


        envelope.gain.setValueAtTime(
            0,
            now
        );


        envelope.gain.linearRampToValueAtTime(
            0.18,
            now + 0.08
        );


        envelope.gain.exponentialRampToValueAtTime(
            0.001,
            now + 1.15
        );


        oscillator.connect(
            envelope
        );


        envelope.connect(
            masterGain
        );


        oscillator.start(
            now
        );


        oscillator.stop(
            now + 1.2
        );

    }


    function musicTick() {

        if (!musicPlaying) {

            return;

        }


        playNote(
            melody[
                musicStep %
                melody.length
            ]
        );


        musicStep += 1;

    }


    async function toggleRufus() {

        initializeAudio();


        if (!audioContext) {

            if (musicLabel) {

                musicLabel.textContent =
                    "Audio unavailable";

            }

            return;

        }


        if (
            audioContext.state ===
            "suspended"
        ) {

            await audioContext.resume();

        }


        if (musicPlaying) {

            musicPlaying =
                false;


            clearInterval(
                musicTimer
            );


            musicTimer =
                null;


            visualizer?.classList.remove(
                "playing"
            );


            musicButton?.classList.remove(
                "is-playing"
            );


            musicButton?.setAttribute(
                "aria-pressed",
                "false"
            );


            if (musicLabel) {

                musicLabel.textContent =
                    "Ambient mode";

            }


            if (musicButton) {

                musicButton.textContent =
                    "▶";

            }


            return;

        }


        musicPlaying =
            true;


        visualizer?.classList.add(
            "playing"
        );


        musicButton?.classList.add(
            "is-playing"
        );


        musicButton?.setAttribute(
            "aria-pressed",
            "true"
        );


        if (musicLabel) {

            musicLabel.textContent =
                "Playing";

        }


        if (musicButton) {

            musicButton.textContent =
                "Ⅱ";

        }


        musicStep =
            Math.floor(
                Math.random()
                *
                melody.length
            );


        musicTick();


        musicTimer =
            setInterval(
                musicTick,
                850
            );

    }


    if (
        musicButton
    ) {

        musicButton.addEventListener(
            "click",
            toggleRufus
        );

    }


    if (
        musicVolume
    ) {

        musicVolume.addEventListener(
            "input",
            () => {

                initializeAudio();


                if (
                    masterGain
                ) {

                    masterGain.gain.value =
                        Number(
                            musicVolume.value
                        );

                }

            }
        );

    }


    /*
     * ---------------------------------------------------------
     * Fynelet
     * ---------------------------------------------------------
     */


    function hashString(
        value
    ) {

        let hash =
            0;


        for (
            let index = 0;
            index < value.length;
            index++
        ) {

            hash =
                (
                    (
                        hash << 5
                    )
                    -
                    hash
                    +
                    value.charCodeAt(
                        index
                    )
                )
                |
                0;

        }


        return Math.abs(
            hash
        );

    }


    function drawFallbackPixellet(
        canvas,
        query
    ) {

        const context =
            canvas.getContext(
                "2d"
            );


        context.clearRect(
            0,
            0,
            48,
            48
        );


        const seed =
            hashString(
                query
            );


        const palette = [

            "#FFD43B",

            "#FF9F1C",

            "#9B5DE5",

            "#00D9FF",

            "#5CE65C",

            "#FF4FD8"

        ];


        context.fillStyle =
            "#11172C";


        context.fillRect(
            0,
            0,
            48,
            48
        );


        for (
            let row = 0;
            row < 8;
            row++
        ) {

            for (
                let column = 0;
                column < 8;
                column++
            ) {

                const value =
                    (
                        seed
                        +
                        row * 31
                        +
                        column * 17
                    )
                    % 11;


                if (
                    value < 6
                ) {

                    context.fillStyle =
                        palette[
                            (
                                value
                                +
                                seed
                            )
                            %
                            palette.length
                        ];


                    context.fillRect(
                        column * 6,
                        row * 6,
                        6,
                        6
                    );

                }

            }

        }


        context.fillStyle =
            "#070A18";


        context.fillRect(
            12,
            15,
            6,
            6
        );


        context.fillRect(
            30,
            15,
            6,
            6
        );


        context.fillStyle =
            "#FFFFFF";


        context.fillRect(
            13,
            15,
            3,
            3
        );


        context.fillRect(
            31,
            15,
            3,
            3
        );

    }


    function drawPixelatedImage(
        canvas,
        dataUrl
    ) {

        const context =
            canvas.getContext(
                "2d"
            );


        const tiny =
            document.createElement(
                "canvas"
            );


        tiny.width =
            48;


        tiny.height =
            48;


        const tinyContext =
            tiny.getContext(
                "2d"
            );


        tinyContext.imageSmoothingEnabled =
            false;


        const image =
            new Image();


        image.onload =
            () => {

                const sourceSize =
                    Math.min(
                        image.naturalWidth,
                        image.naturalHeight
                    );


                const sourceX =
                    (
                        image.naturalWidth
                        -
                        sourceSize
                    )
                    / 2;


                const sourceY =
                    (
                        image.naturalHeight
                        -
                        sourceSize
                    )
                    / 2;


                tinyContext.clearRect(
                    0,
                    0,
                    48,
                    48
                );


                tinyContext.drawImage(
                    image,
                    sourceX,
                    sourceY,
                    sourceSize,
                    sourceSize,
                    0,
                    0,
                    48,
                    48
                );


                canvas.width =
                    48;


                canvas.height =
                    48;


                context.clearRect(
                    0,
                    0,
                    48,
                    48
                );


                context.imageSmoothingEnabled =
                    false;


                context.drawImage(
                    tiny,
                    0,
                    0
                );

            };


        image.onerror =
            () => {

                drawFallbackPixellet(
                    canvas,
                    "FyneApple"
                );

            };


        image.src =
            dataUrl;

    }


    async function initializePixellet() {

        const container =
            document.getElementById(
                "pixellet"
            );


        const canvas =
            document.getElementById(
                "pixellet-canvas"
            );


        const queryLabel =
            document.getElementById(
                "pixellet-query"
            );


        const sourceLabel =
            document.getElementById(
                "pixellet-source"
            );


        if (
            !container ||
            !canvas ||
            !queryLabel
        ) {

            return;

        }


        const query =
            container.dataset.query ||
            "";


        if (!query) {

            return;

        }


        queryLabel.textContent =
            query;


        drawFallbackPixellet(
            canvas,
            query
        );


        container.classList.remove(
            "hidden"
        );


        try {

            const response =
                await fetch(
                    `/api/pixellet?q=${encodeURIComponent(query)}`
                );


            if (
                !response.ok
            ) {

                throw new Error(
                    "Pixellet request failed."
                );

            }


            const result =
                await response.json();


            if (
                !result.image
            ) {

                throw new Error(
                    "No image returned."
                );

            }


            drawPixelatedImage(
                canvas,
                result.image
            );


            if (
                sourceLabel
            ) {

                sourceLabel.textContent =
                    "live image";

            }


        } catch {

            if (
                sourceLabel
            ) {

                sourceLabel.textContent =
                    "Fynelet";

            }

        }

    }


    initializePixellet();

})();