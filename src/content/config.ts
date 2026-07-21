import { defineCollection, z } from 'astro:content';

const articleCollection = defineCollection({
  type: 'content',
  schema: z.object({
    title: z.string(),
    description: z.string(),
    pubDate: z.coerce.date(),
    updatedDate: z.coerce.date().optional(),
    category: z.string(),
    tags: z.array(z.string()).default([]),
    draft: z.boolean().default(false),
    products: z.array(z.object({
      name: z.string(),
      price: z.string().optional(),
      amazonUrl: z.string().optional(),
      rating: z.number().min(0).max(5).optional().nullable(),
    })).default([]),
    articleType: z.enum(['review', 'comparison', 'ranking', 'guide', 'redirect']).default('review'),
    aiAssisted: z.boolean().default(true),
  }),
});

export const collections = {
  articles: articleCollection,
};

export async function getSortedPosts() {
  const { getCollection } = await import('astro:content');
  const posts = await getCollection('articles');
  return posts
    .filter((post: any) => !post.data.draft)
    .sort((a: any, b: any) => b.data.pubDate.getTime() - a.data.pubDate.getTime());
}
