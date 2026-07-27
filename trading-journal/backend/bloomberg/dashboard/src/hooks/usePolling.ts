import useSWR from 'swr';

const fetcher = async (url: string) => {
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Request failed: ${res.status}`);
  }
  return res.json();
};

export function usePollingState() {
  const { data, error, isLoading } = useSWR('/api/state', fetcher, { refreshInterval: 5000 });
  return { data, error, isLoading };
}
