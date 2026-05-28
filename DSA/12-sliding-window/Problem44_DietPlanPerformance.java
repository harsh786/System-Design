/**
 * Problem 44: Diet Plan Performance (LeetCode 1176)
 * 
 * Approach: Fixed window of size k. If sum < lower: -1 point. If sum > upper: +1 point.
 * Window invariant: window size == k, track running sum.
 * 
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like scoring system health over rolling windows -
 * penalty for underperformance, reward for exceeding targets.
 */
public class Problem44_DietPlanPerformance {
    public static int dietPlanPerformance(int[] calories, int k, int lower, int upper) {
        int sum = 0, points = 0;
        for (int i = 0; i < calories.length; i++) {
            sum += calories[i];
            if (i >= k) sum -= calories[i - k];
            if (i >= k - 1) {
                if (sum < lower) points--;
                else if (sum > upper) points++;
            }
        }
        return points;
    }

    public static void main(String[] args) {
        System.out.println(dietPlanPerformance(new int[]{1,2,3,4,5}, 1, 3, 3)); // 0
        System.out.println(dietPlanPerformance(new int[]{3,2}, 2, 0, 1));        // 1
        System.out.println(dietPlanPerformance(new int[]{6,5,0,0}, 2, 1, 5));    // 0
    }
}
