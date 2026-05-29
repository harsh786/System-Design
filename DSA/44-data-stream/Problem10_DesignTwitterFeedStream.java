import java.util.*;

public class Problem10_DesignTwitterFeedStream {
    // 355. Design Twitter (simplified feed stream).
    
    Map<Integer, Set<Integer>> follows = new HashMap<>();
    Map<Integer, List<int[]>> tweets = new HashMap<>(); // userId -> [(time, tweetId)]
    int time = 0;
    
    public void postTweet(int userId, int tweetId) {
        tweets.computeIfAbsent(userId, k -> new ArrayList<>()).add(new int[]{time++, tweetId});
    }
    
    public List<Integer> getNewsFeed(int userId) {
        PriorityQueue<int[]> pq = new PriorityQueue<>((a,b) -> b[0] - a[0]);
        Set<Integer> users = follows.getOrDefault(userId, new HashSet<>());
        users.add(userId);
        for (int u : users) {
            List<int[]> t = tweets.getOrDefault(u, Collections.emptyList());
            for (int[] tw : t) pq.offer(tw);
        }
        users.remove(userId); // don't persist self-follow
        List<Integer> res = new ArrayList<>();
        while (!pq.isEmpty() && res.size() < 10) res.add(pq.poll()[1]);
        return res;
    }
    
    public void follow(int followerId, int followeeId) {
        follows.computeIfAbsent(followerId, k -> new HashSet<>()).add(followeeId);
    }
    
    public void unfollow(int followerId, int followeeId) {
        follows.getOrDefault(followerId, new HashSet<>()).remove(followeeId);
    }
    
    public static void main(String[] args) {
        Problem10_DesignTwitterFeedStream sol = new Problem10_DesignTwitterFeedStream();
        sol.postTweet(1, 5);
        System.out.println(sol.getNewsFeed(1)); // [5]
        sol.follow(1, 2);
        sol.postTweet(2, 6);
        System.out.println(sol.getNewsFeed(1)); // [6, 5]
        sol.unfollow(1, 2);
        System.out.println(sol.getNewsFeed(1)); // [5]
    }
}
