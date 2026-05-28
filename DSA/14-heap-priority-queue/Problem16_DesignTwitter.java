import java.util.*;

/**
 * Problem 16: Design Twitter (LeetCode 355)
 * 
 * Approach: Each user has a list of tweets with timestamps. getNewsFeed merges
 * K sorted lists (followees' tweets) using min-heap, return top 10.
 * 
 * Time Complexity: O(K log K) for getNewsFeed where K = followees
 * Space Complexity: O(Users + Tweets + Follows)
 * 
 * Production Analogy: Social media feed aggregation - merging activity streams
 * from followed accounts into a personalized timeline.
 */
public class Problem16_DesignTwitter {
    
    private int timestamp = 0;
    private Map<Integer, List<int[]>> tweets = new HashMap<>();
    private Map<Integer, Set<Integer>> follows = new HashMap<>();
    
    public void postTweet(int userId, int tweetId) {
        tweets.computeIfAbsent(userId, k -> new ArrayList<>()).add(new int[]{timestamp++, tweetId});
    }
    
    public List<Integer> getNewsFeed(int userId) {
        PriorityQueue<int[]> maxHeap = new PriorityQueue<>((a, b) -> b[0] - a[0]);
        Set<Integer> followees = follows.getOrDefault(userId, new HashSet<>());
        followees.add(userId); // include self
        
        for (int fid : followees) {
            List<int[]> userTweets = tweets.getOrDefault(fid, Collections.emptyList());
            for (int[] t : userTweets) maxHeap.offer(t);
        }
        followees.remove(userId);
        
        List<Integer> result = new ArrayList<>();
        int count = 0;
        while (!maxHeap.isEmpty() && count < 10) {
            result.add(maxHeap.poll()[1]);
            count++;
        }
        return result;
    }
    
    public void follow(int followerId, int followeeId) {
        follows.computeIfAbsent(followerId, k -> new HashSet<>()).add(followeeId);
    }
    
    public void unfollow(int followerId, int followeeId) {
        follows.getOrDefault(followerId, new HashSet<>()).remove(followeeId);
    }
    
    public static void main(String[] args) {
        Problem16_DesignTwitter twitter = new Problem16_DesignTwitter();
        twitter.postTweet(1, 5);
        System.out.println(twitter.getNewsFeed(1)); // [5]
        twitter.follow(1, 2);
        twitter.postTweet(2, 6);
        System.out.println(twitter.getNewsFeed(1)); // [6, 5]
        twitter.unfollow(1, 2);
        System.out.println(twitter.getNewsFeed(1)); // [5]
    }
}
