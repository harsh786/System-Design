/**
 * Problem 33: Candy
 * Each child has a rating. Give candies such that higher-rated children get more
 * than neighbors. Minimize total candies.
 * 
 * Production Analogy: Like SLA-based resource allocation - services with higher
 * priority must get more resources than adjacent lower-priority ones.
 * 
 * O(n) time, O(n) space - two passes (left-to-right, right-to-left)
 */
public class Problem33_Candy {

    public static int candy(int[] ratings) {
        int n = ratings.length;
        int[] candies = new int[n];
        java.util.Arrays.fill(candies, 1);
        for (int i = 1; i < n; i++)
            if (ratings[i] > ratings[i-1]) candies[i] = candies[i-1] + 1;
        for (int i = n - 2; i >= 0; i--)
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
