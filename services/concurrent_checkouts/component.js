class ConcurrentCheckouts extends HTMLElement {
    constructor() {
        super();

        this.attachShadow({ mode: "open" });

        this.baseUrl = "";
        this.apiUrl = "";
        this.templateUrl = "";
    }


    async connectedCallback() {
        /*
         * Prefer an explicitly supplied base-url if there is one:
         *
         * <concurrent-checkouts
         *     base-url="https://tufts-libraries-alma-self-service-stage-app.library.tufts.edu">
         * </concurrent-checkouts>
         *
         * Otherwise derive the server URL from component.js itself:
         *
         * https://.../concurrent_checkouts/component.js
         *                ↓
         * https://...
         */

        const suppliedBaseUrl = this.getAttribute("base-url");

        if (suppliedBaseUrl) {
            this.baseUrl = suppliedBaseUrl.replace(/\/+$/, "");
        } else {
            const scriptUrl = document.currentScript?.src || "";

            this.baseUrl = scriptUrl.replace(
                /\/concurrent_checkouts\/component\.js(?:\?.*)?$/,
                ""
            );
        }


        if (!this.baseUrl) {
            console.error(
                "Concurrent Checkouts: unable to determine application base URL."
            );

            return;
        }


        this.apiUrl =
            `${this.baseUrl}/concurrent_checkouts/upload`;

        this.templateUrl =
            `${this.baseUrl}/concurrent_checkouts/component-template`;


        await this.loadTemplate();
    }


    // ================================================================
    // Template
    // ================================================================

    async loadTemplate() {
        try {
            const response = await fetch(
                this.templateUrl,
                {
                    method: "GET"
                }
            );


            if (!response.ok) {
                throw new Error(
                    `Failed to load template: HTTP ${response.status}`
                );
            }


            const html = await response.text();


            const templateWrapper =
                document.createElement("div");

            templateWrapper.innerHTML =
                html.trim();


            const template =
                templateWrapper.querySelector("template");


            if (!template) {
                throw new Error(
                    "No <template> element found in component-template response."
                );
            }


            this.shadowRoot.innerHTML = "";


            this.shadowRoot.appendChild(
                template.content.cloneNode(true)
            );


            await this.injectStyles();

            this.injectHourglass();

            this.attachEventListeners();

        } catch (error) {
            console.error(
                "Concurrent Checkouts: error loading component template:",
                error
            );
        }
    }


    // ================================================================
    // Shared styles
    // ================================================================

    async injectStyles() {
        try {
            const cssUrl =
                `${this.baseUrl}/static/styles.css`;


            const response = await fetch(
                cssUrl,
                {
                    method: "GET"
                }
            );


            if (!response.ok) {
                throw new Error(
                    `Failed to load CSS: HTTP ${response.status}`
                );
            }


            const cssText =
                await response.text();


            const styleTag =
                document.createElement("style");

            styleTag.textContent =
                cssText;


            this.shadowRoot.appendChild(
                styleTag
            );

        } catch (error) {
            /*
             * Don't prevent the component from working merely because
             * shared CSS couldn't be fetched.
             */
            console.error(
                "Concurrent Checkouts: error injecting styles:",
                error
            );
        }
    }


    // ================================================================
    // Hourglass
    // ================================================================

    injectHourglass() {
        /*
         * Don't add a duplicate if the component template already
         * contains one.
         */

        if (
            this.shadowRoot.getElementById(
                "hourglass"
            )
        ) {
            return;
        }


        const wrapper =
            document.createElement("div");


        wrapper.innerHTML = `
            <div
                id="hourglass"
                style="display: none;"
            >
                <div class="spinner"></div>
            </div>
        `;


        this.shadowRoot.appendChild(
            wrapper
        );
    }


    showHourglass() {
        const hourglass =
            this.shadowRoot.getElementById(
                "hourglass"
            );


        if (hourglass) {
            hourglass.style.display =
                "block";
        }
    }


    hideHourglass() {
        const hourglass =
            this.shadowRoot.getElementById(
                "hourglass"
            );


        if (hourglass) {
            hourglass.style.display =
                "none";
        }
    }


    // ================================================================
    // Upload form
    // ================================================================

    attachEventListeners() {
        const uploadForm =
            this.shadowRoot.getElementById(
                "uploadForm"
            );


        if (!uploadForm) {
            console.error(
                "Concurrent Checkouts: upload form not found in template."
            );

            return;
        }


        /*
         * Make sure the form points at the isolated service endpoint.
         */
        uploadForm.action =
            this.apiUrl;


        uploadForm.addEventListener(
            "submit",
            event => this.handleFormSubmit(event)
        );
    }


    async handleFormSubmit(event) {
        event.preventDefault();


        this.showHourglass();


        const form =
            event.target;


        const formData =
            new FormData(form);


        try {
            const response = await fetch(
                this.apiUrl,
                {
                    method: "POST",
                    body: formData
                }
            );


            if (!response.ok) {
                let message =
                    `Upload failed: HTTP ${response.status}`;


                /*
                 * Your Flask endpoint returns JSON errors, so try to
                 * display/log the server's actual error.
                 */
                try {
                    const errorData =
                        await response.json();


                    if (errorData?.error) {
                        message =
                            errorData.error;
                    }

                } catch (_) {
                    /*
                     * Response wasn't JSON.
                     */
                }


                throw new Error(
                    message
                );
            }


            const blob =
                await response.blob();


            const objectUrl =
                window.URL.createObjectURL(
                    blob
                );


            const link =
                document.createElement("a");


            link.href =
                objectUrl;

            link.download =
                "Counts.xlsx";


            document.body.appendChild(
                link
            );


            link.click();


            document.body.removeChild(
                link
            );


            window.URL.revokeObjectURL(
                objectUrl
            );

        } catch (error) {
            console.error(
                "Concurrent Checkouts: error during file processing:",
                error
            );

        } finally {
            this.hideHourglass();
        }
    }
}


// ================================================================
// Register custom element
// ================================================================


customElements.define("concurrent-checkouts", ConcurrentCheckouts);