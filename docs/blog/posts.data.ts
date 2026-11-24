import { createContentLoader } from "vitepress";

export interface Post {
  title: string;
  url: string;
  date: string;
  summary: string;
  order: number;
}

declare const data: Post[];
export { data };

// Every Markdown file in this folder except the index is a post; the newest comes first.
export default createContentLoader("blog/*.md", {
  transform(raw): Post[] {
    return raw
      .filter((page) => page.frontmatter.date)
      .map((page) => ({
        title: page.frontmatter.title,
        url: page.url,
        date: new Date(page.frontmatter.date).toISOString().slice(0, 10),
        summary: page.frontmatter.summary ?? "",
        order: page.frontmatter.order ?? 99,
      }))
      // Newest first; posts of the same day in the order their front matter gives.
      .sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : a.order - b.order));
  },
});
