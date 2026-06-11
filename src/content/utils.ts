import type { CollectionEntry } from 'astro:content';

export async function getSortedPosts(): Promise<CollectionEntry<'articles'>[]> {
  const { getCollection } = await import('astro:content');
  const posts = await getCollection('articles');
  return posts
    .filter(post => !post.data.draft)
    .sort((a, b) => b.data.pubDate.getTime() - a.data.pubDate.getTime());
}

export async function getPostsByCategory(category: string): Promise<CollectionEntry<'articles'>[]> {
  const allPosts = await getSortedPosts();
  return allPosts.filter(post => post.data.category === category);
}

export async function getRecentPosts(count: number = 5): Promise<CollectionEntry<'articles'>[]> {
  const allPosts = await getSortedPosts();
  return allPosts.slice(0, count);
}
