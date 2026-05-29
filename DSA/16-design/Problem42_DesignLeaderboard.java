import java.util.*;

/**
 * Problem 42: Design A Leaderboard
 * 
 * API Contract:
 * - addScore(playerId, score): Add score to player's total
 * - top(K): Return sum of top K scores
 * - reset(playerId): Reset player's score to 0
 * 
 * Complexity: addScore O(1), top O(n log K), reset O(1)
 * Data Structure: HashMap + sorting/heap for top-K
 * 
 * Production Analogy: Gaming leaderboards, sales ranking dashboards,
 * competitive programming standings, employee performance rankings
 */
public class Problem42_DesignLeaderboard {

    static class Leaderboard {
        private Map<Integer, Integer> scores;

        public Leaderboard() { scores = new HashMap<>(); }

        public void addScore(int playerId, int score) {
            scores.merge(playerId, score, Integer::sum);
        }

        public int top(int K) {
            PriorityQueue<Integer> pq = new PriorityQueue<>(); // min-heap of size K
            for (int s : scores.values()) {
                pq.offer(s);
                if (pq.size() > K) pq.poll();
            }
            int sum = 0;
            while (!pq.isEmpty()) sum += pq.poll();
            return sum;
        }

        public void reset(int playerId) { scores.remove(playerId); }
    }

    public static void main(String[] args) {
        Leaderboard lb = new Leaderboard();
        lb.addScore(1, 73);
        lb.addScore(2, 56);
        lb.addScore(3, 39);
        lb.addScore(4, 51);
        lb.addScore(5, 4);
        assert lb.top(1) == 73;
        assert lb.top(3) == 73 + 56 + 51;
        lb.reset(1);
        lb.addScore(2, 51); // player 2 now has 107
        assert lb.top(1) == 107;

        System.out.println("All tests passed!");
    }
}
