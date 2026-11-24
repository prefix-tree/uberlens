---
title: Blog
titleTemplate: UberSeek
sidebar: false
aside: false
---

<script setup>
import { withBase } from "vitepress";
import { data as posts } from "./posts.data.ts";
</script>

# Blog

What we built, what we measured, and what went wrong on the way.

<ul class="blog-list">
  <li v-for="post in posts" :key="post.url">
    <time :datetime="post.date">{{ post.date }}</time>
    <a class="title" :href="withBase(post.url)">{{ post.title }}</a>
    <p>{{ post.summary }}</p>
  </li>
</ul>
