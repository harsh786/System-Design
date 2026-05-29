import java.util.*;

public class Problem22_DesignALeaderboard {
    // 1244. Design A Leaderboard.
    
    Map<Integer, Integer> scores = new HashMap<>();
    
    public void addScore(int playerId, int score) { scores.merge(playerId, score, Integer::sum); }
    
    public int top(int K) {
        PriorityQueue<Integer> pq = new PriorityQueue<>();
        for (int s : scores.values()) {
            pq.offer(s);
            if (pq.size() > K) pq.poll();
        }
        int sum = 0;
        while (!pq.isEmpty()) sum += pq.poll();
        return sum;
    }
    
    public void reset(int playerId) { scores.remove(playerId); }
    
    public static void main(String[] args) {
        Problem22_DesignALeaderboard sol = new Problem22_DesignALeaderboard();
        sol.addScore(1, 73); sol.addScore(2, 56); sol.addScore(3, 39);
        sol.addScore(4, 51); sol.addScore(5, 4);
        System.out.println(sol.top(1)); // 73
        sol.reset(1);
        System.out.println(sol.top(1)); // 56
    }
}
