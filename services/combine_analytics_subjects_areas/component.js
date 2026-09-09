class SQLGenerator extends HTMLElement {
  constructor() {
      super();

      this.attachShadow({ mode: "open" });

      const scriptUrl = document.currentScript?.src || "";

      this.componentBaseUrl = scriptUrl.replace(
          /\/component\.js.*$/,
          ""
      );

      this.baseUrl = new URL(
          scriptUrl
      ).origin;
  }

  async connectedCallback() {
    await this.loadTemplate();
  }

  async loadTemplate() {
    const response = await fetch(
    `${this.componentBaseUrl}/component-template`
);
    const html = await response.text();

    const doc = new DOMParser().parseFromString(html, "text/html");
    const template = doc.querySelector("#alma-analytics-sql-generator");

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          font-family: Arial, sans-serif;
        }

        textarea {
          max-width: 100%;
          font-family: monospace;
        }

        button {
          cursor: pointer;
        }

        #output textarea {
          width: 100%;
          min-height: 18rem;
        }

        .error {
          color: #b00020;
          font-weight: bold;
          margin-top: 1rem;
        }
      </style>
      ${template ? template.innerHTML : html}
    `;

    this.rewriteHelpLinks();
    this.attachSubmitHandler();
    this.attachHelpLinkHandler();
  }

  rewriteHelpLinks() {
    this.shadowRoot.querySelectorAll('a[href^="/"]').forEach((link) => {
      link.href = `${this.baseUrl}${link.getAttribute("href")}`;
    });

    this.shadowRoot.querySelectorAll('img[src^="/"]').forEach((img) => {
      img.src = `${this.baseUrl}${img.getAttribute("src")}`;
    });
  }

  attachSubmitHandler() {
    const form = this.shadowRoot.querySelector("#uploadForm");
    if (!form) return;

    form.addEventListener("submit", async (event) => {
      event.preventDefault();

      const button = form.querySelector('button[type="submit"]');
      if (button) {
        button.disabled = true;
        button.textContent = "Processing...";
      }

      this.clearOutput();

      try {
        const formData = new FormData(form);

      const response = await fetch(
          `${this.componentBaseUrl}/process_sql`,
          {
              method: "POST",
              body: formData
          }
      );

        if (!response.ok) {
          throw new Error(`Server returned ${response.status}`);
        }

        const returnedHtml = await response.text();
        this.displayReturnedOutput(returnedHtml);
      } catch (error) {
        this.showError(error);
      } finally {
        if (button) {
          button.disabled = false;
          button.textContent = "Process SQL";
        }
      }
    });
  }

  attachHelpLinkHandler() {
  const base = (this.baseUrl || "").replace(/\/+$/, "");

  // 1) Rewrite help icon image src to absolute Flask URL
  this.shadowRoot.querySelectorAll("img.help-icon[src]").forEach(img => {
    const src = img.getAttribute("src") || "";

    // Only rewrite root-relative URLs
    if (src.startsWith("/")) {
      img.setAttribute("src", `${base}${src}`);
    }
  });
}
  clearOutput() {
    this.shadowRoot.querySelector("#output")?.remove();
    this.shadowRoot.querySelector(".error")?.remove();
  }

  displayReturnedOutput(returnedHtml) {
    const doc = new DOMParser().parseFromString(returnedHtml, "text/html");
    const returnedOutput = doc.querySelector("#output");

    if (!returnedOutput) {
      this.showError(new Error("No output SQL was returned."));
      return;
    }

    const form = this.shadowRoot.querySelector("#uploadForm");
    form.insertAdjacentElement("afterend", returnedOutput);
  }

  showError(error) {
    const form = this.shadowRoot.querySelector("#uploadForm");
    const div = document.createElement("div");
    div.className = "error";
    div.textContent = `Error: ${error.message}`;
    form.insertAdjacentElement("afterend", div);
  }
}

customElements.define("alma-analytics-sql-generator", SQLGenerator);