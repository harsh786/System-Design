import java.util.*;

/**
 * Problem 36: Online Election
 * 
 * Given persons[] and times[], at each time[i] person[i] gets a vote.
 * Query: who was leading at time t?
 * 
 * Approach: Precompute leader at each timestamp. Binary search for query time.
 * 
 * Time: O(n) init, O(log n) query, Space: O(n)
 * 
 * Production Analogy: Finding the leading A/B test variant at any point in time
 * for time-travel analytics queries.
 */
public class Problem36_OnlineElection {
    private int[] times;
    private int[] leaders;

    public Problem36_OnlineElection(int[] persons, int[] times) {
        this.times = times;
        int n = persons.length;
        leaders = new int[n];
        Map<Integer, Integer> votes = new HashMap<>();
        int leader = -1, maxVotes = 0;
        for (int i = 0; i < n; i++) {
            int v = votes.merge(persons[i], 1, Integer::sum);
            if (v >= maxVotes) { leader = persons[i]; maxVotes = v; }
            leaders[i] = leader;
        }
    }

    public int q(int t) {
        // Find rightmost time <= t
        int lo = 0, hi = times.length - 1;
        while (lo < hi) {
            int mid = lo + (hi - lo + 1) / 2;
            if (times[mid] <= t) lo = mid;
            else hi = mid - 1;
        }
        return leaders[lo];
    }

    public static void main(String[] args) {
        Problem36_OnlineElection election = new Problem36_OnlineElection(
            new int[]{0,1,1,0,0,1,0}, new int[]{0,5,10,15,20,25,30});
        System.out.println(election.q(3));  // 0
        System.out.println(election.q(12)); // 1
        System.out.println(election.q(25)); // 1
        System.out.println(election.q(15)); // 0
        System.out.println(election.q(24)); // 0
        System.out.println(election.q(8));  // 1
    }
}
