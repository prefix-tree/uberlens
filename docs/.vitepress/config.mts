import { defineConfig } from "vitepress";

// The site is served from "/" on its own domain and from "/<repo>/" on GitHub Pages; the workflow sets DOCS_BASE.
const base = process.env.DOCS_BASE ? `${process.env.DOCS_BASE.replace(/\/$/, "")}/` : "/";
const repo = "https://github.com/prefix-tree/uberseek";

export default defineConfig({
  title: "UberSeek",
  description:
    "A programmable environment for exploring video: an agent writes small programs to search and measure footage, asks to be shown images where a judgment needs eyes, and picks the right moments.",
  base,
  cleanUrls: true,
  // The archive is frozen research for the repository, not the site.
  srcExclude: ["archive/**"],
  lastUpdated: true,
  markdown: { theme: { light: "github-light", dark: "github-dark" } },
  head: [
    ["link", { rel: "icon", type: "image/svg+xml", href: `${base}favicon.svg` }],
    ["link", { rel: "preconnect", href: "https://fonts.gstatic.com", crossorigin: "" }],
    [
      "link",
      {
        rel: "stylesheet",
        href: "https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Inter:wght@400;450;500;600&display=swap",
      },
    ],
  ],
  themeConfig: {
    siteTitle: "uberseek",
    nav: [
      { text: "Design", link: "/design", activeMatch: "^/design" },
      { text: "Research", link: `${repo}/tree/main/docs/archive` },
      { text: "UberScene", link: "https://uberscene.prefixtree.xyz/" },
    ],
    sidebar: [
      {
        text: "UberSeek",
        items: [
          { text: "Overview", link: "/" },
          { text: "Design", link: "/design" },
        ],
      },
      {
        text: "Elsewhere",
        items: [
          { text: "Research archive", link: `${repo}/tree/main/docs/archive` },
          { text: "UberScene", link: "https://uberscene.prefixtree.xyz/" },
        ],
      },
    ],
    outline: { level: [2, 3], label: "On this page" },
    socialLinks: [{ icon: "github", link: repo }],
    search: { provider: "local" },
    editLink: { pattern: `${repo}/edit/main/docs/:path`, text: "Edit this page" },
    footer: { message: "MPL-2.0", copyright: "Prefix Tree" },
  },
});
