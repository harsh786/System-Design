import java.util.*;

public class Problem30_DesignALeaderboard {
    // LC 1244: Design leaderboard with addScore, top(K), reset
    Map<Integer, Integer> scores;
    TreeMap<Integer, Integer> sortedScores;

    public Problem30_DesignALeaderboard() {
        scores = new HashMap<>();
        sortedScores = new TreeMap<>(Collections.reverseOrder());
    }

    public void addScore(int playerId, int score) {
        int old = scores.getOrDefault(playerId, 0);
        if (old > 0) { sortedScores.merge(old, -1, Integer::sum); if (sortedScores.get(old) == 0) sortedScores.remove(old); }
        scores.put(playerId, old + score);
        sortedScores.merge(old + score, 1, Integer::sum);
    }

    public int top(int K) {
        int sum = 0, remaining = K;
        for (var e : sortedScores.entrySet()) {
            int take = Math.min(remaining, e.getValue());
            sum += e.getKey() * take;
            remaining -= take;
            if (remaining == 0) break;
        }
        return sum;
    }

    public void reset(int playerId) {
        int old = scores.get(playerId);
        sortedScores.merge(old, -1, Integer::sum);
        if (sortedScores.get(old) == 0) sortedScores.remove(old);
        scores.put(playerId, 0);
    }

    public static void main(String[] args) {
        Problem30_DesignALeaderboard lb = new Problem30_DesignALeaderboard();
        lb.addScore(1, 73); lb.addScore(2, 56); lb.addScore(3, 39);
        lb.addScore(4, 51); lb.addScore(5, 4);
        System.out.println(lb.top(1)); // 73
        lb.reset(1); lb.reset(2);
        lb.addScore(2, 51);
        System.out.println(lb.top(3)); // 141
    }
}
