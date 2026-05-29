import java.util.*;

/**
 * Problem 7: Design Twitter
 * 
 * API Contract:
 * - postTweet(userId, tweetId): Compose a new tweet
 * - getNewsFeed(userId): Get 10 most recent tweets from user + followees
 * - follow(followerId, followeeId): Follow a user
 * - unfollow(followerId, followeeId): Unfollow a user
 * 
 * Complexity: getNewsFeed O(N log 10) where N = followees, others O(1)
 * Data Structure: HashMap for follows, HashMap for tweets per user, Min-Heap merge
 * 
 * Production Analogy: Twitter/X timeline service, news feed ranking at Facebook,
 * activity feed aggregation in social platforms
 */
public class Problem07_DesignTwitter {

    static class Twitter {
        private int timestamp;
        private Map<Integer, Set<Integer>> follows;
        private Map<Integer, List<int[]>> tweets; // userId -> [(time, tweetId)]

        public Twitter() {
            timestamp = 0;
            follows = new HashMap<>();
            tweets = new HashMap<>();
        }

        public void postTweet(int userId, int tweetId) {
            tweets.computeIfAbsent(userId, k -> new ArrayList<>()).add(new int[]{timestamp++, tweetId});
        }

        public List<Integer> getNewsFeed(int userId) {
            // Max-heap by timestamp
            PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> b[0] - a[0]);
            Set<Integer> users = new HashSet<>();
            users.add(userId);
            if (follows.containsKey(userId)) users.addAll(follows.get(userId));

            for (int uid : users) {
                List<int[]> userTweets = tweets.getOrDefault(uid, Collections.emptyList());
                for (int[] t : userTweets) pq.offer(t);
            }

            List<Integer> result = new ArrayList<>();
            while (!pq.isEmpty() && result.size() < 10) {
                result.add(pq.poll()[1]);
            }
            return result;
        }

        public void follow(int followerId, int followeeId) {
            if (followerId == followeeId) return;
            follows.computeIfAbsent(followerId, k -> new HashSet<>()).add(followeeId);
        }

        public void unfollow(int followerId, int followeeId) {
            if (follows.containsKey(followerId))
                follows.get(followerId).remove(followeeId);
        }
    }

    public static void main(String[] args) {
        Twitter twitter = new Twitter();
        twitter.postTweet(1, 5);
        assert twitter.getNewsFeed(1).equals(List.of(5));
        twitter.follow(1, 2);
        twitter.postTweet(2, 6);
        assert twitter.getNewsFeed(1).equals(List.of(6, 5));
        twitter.unfollow(1, 2);
        assert twitter.getNewsFeed(1).equals(List.of(5));

        // Edge: user with no tweets
        assert twitter.getNewsFeed(99).isEmpty();

        // Edge: more than 10 tweets
        Twitter t2 = new Twitter();
        for (int i = 0; i < 15; i++) t2.postTweet(1, i);
        assert t2.getNewsFeed(1).size() == 10;
        assert t2.getNewsFeed(1).get(0) == 14; // most recent

        System.out.println("All tests passed!");
    }
}
