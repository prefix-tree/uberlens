import { defineConfig } from "vitepress";

// The site is served from "/" on its own domain and from "/<repo>/" on GitHub Pages; the workflow sets DOCS_BASE.
const base = process.env.DOCS_BASE ? `${process.env.DOCS_BASE.replace(/\/$/, "")}/` : "/";
const repo = "https://github.com/prefix-tree/uberseek";
const site = "https://uberseek.prefixtree.xyz";
const tagline = "Video exploration for AI agents: find the moment, look only where it matters, cut a checked clip.";

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
    ["meta", { property: "og:type", content: "website" }],
    ["meta", { property: "og:site_name", content: "UberSeek" }],
    ["meta", { property: "og:title", content: "UberSeek" }],
    ["meta", { property: "og:description", content: tagline }],
    ["meta", { property: "og:image", content: `${site}/og.png` }],
    ["meta", { name: "twitter:card", content: "summary_large_image" }],
    ["meta", { name: "twitter:image", content: `${site}/og.png` }],
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
    logo: { light: "/logo.svg", dark: "/logo-dark.svg", alt: "" },
    siteTitle: "uberseek",
    nav: [
      { text: "Get started", link: "/get-started", activeMatch: "^/get-started" },
      { text: "Design", link: "/design", activeMatch: "^/design" },
      { text: "Results", link: "/results", activeMatch: "^/results" },
      { text: "Blog", link: "/blog/", activeMatch: "^/blog" },
      { text: "Roadmap", link: "/roadmap", activeMatch: "^/roadmap" },
    ],
    sidebar: {
      "/blog/": [],
      "/": [
        {
          text: "UberSeek",
          items: [
            { text: "Overview", link: "/" },
            { text: "Get started", link: "/get-started" },
            { text: "The skill", link: "/skill" },
          ],
        },
        {
          text: "Project",
          items: [
            { text: "Design", link: "/design" },
            { text: "Results", link: "/results" },
            { text: "Roadmap", link: "/roadmap" },
            { text: "Blog", link: "/blog/" },
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
    },
    outline: { level: [2, 3], label: "On this page" },
    socialLinks: [{ icon: "github", link: repo }],
    search: { provider: "local" },
    editLink: { pattern: `${repo}/edit/main/docs/:path`, text: "Edit this page" },
    footer: { message: "MPL-2.0", copyright: "Prefix Tree" },
  },
});
