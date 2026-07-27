import { createClient } from 'redis';

const globalForRedis = global as unknown as { redisClient: ReturnType<typeof createClient> };

export const redisClient =
  globalForRedis.redisClient 
  createClient({
    url: process.env.REDIS_URL  'redis://localhost:6380'
  });

if (process.env.NODE_ENV !== 'production') globalForRedis.redisClient = redisClient;

redisClient.on('error', (err) => console.error('Redis Client Error', err));

export async function getRedisClient() {
  if (!redisClient.isOpen) {
    try {
      await redisClient.connect();
    } catch (e) {
      console.warn("Failed to connect to Redis. Serving mocks if needed.", e);
    }
  }
  return redisClient;
}
