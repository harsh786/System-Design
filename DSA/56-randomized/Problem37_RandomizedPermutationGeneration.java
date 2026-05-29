import java.util.*;

public class Problem37_RandomizedPermutationGeneration {
    // Generate random permutation of 1..n
    public static int[] randomPermutation(int n) {
        int[] perm = new int[n];
        for (int i = 0; i < n; i++) perm[i] = i + 1;
        Random rand = new Random();
        for (int i = n - 1; i > 0; i--) {
            int j = rand.nextInt(i + 1);
            int tmp = perm[i]; perm[i] = perm[j]; perm[j] = tmp;
        }
        return perm;
    }

    // Knuth shuffle inside-out variant
    public static int[] insideOutShuffle(int n) {
        int[] perm = new int[n];
        Random rand = new Random();
        for (int i = 0; i < n; i++) {
            int j = rand.nextInt(i + 1);
            perm[i] = perm[j];
            perm[j] = i + 1;
        }
        return perm;
    }

    public static void main(String[] args) {
        System.out.println(Arrays.toString(randomPermutation(10)));
        System.out.println(Arrays.toString(insideOutShuffle(10)));
    }
}
