/**
 * Problem 9: Candy (LeetCode 135)
 *
 * Greedy Choice: Two passes - left-to-right ensures right neighbor constraint,
 * right-to-left ensures left neighbor constraint. Take max at each position.
 *
 * Time: O(n), Space: O(n)
 *
 * Production Analogy: Performance bonus allocation where better performers must get more
 * than adjacent lower performers.
 */
public class Problem09_Candy {
    
    public static int candy(int[] ratings) {
        int n = ratings.length;
        int[] candies = new int[n];
        java.util.Arrays.fill(candies, 1);
        for (int i = 1; i < n; i++)
            if (ratings[i] > ratings[i-1]) candies[i] = candies[i-1] + 1;
        for (int i = n-2; i >= 0; i--)
            if (ratings[i] > ratings[i+1]) candies[i] = Math.max(candies[i], candies[i+1] + 1);
        int sum = 0;
        for (int c : candies) sum += c;
        return sum;
    }
    
    public static void main(String[] args) {
        System.out.println(candy(new int[]{1,0,2}));     // 5
        System.out.println(candy(new int[]{1,2,2}));     // 4
        System.out.println(candy(new int[]{1,3,2,2,1})); // 7
    }
}
