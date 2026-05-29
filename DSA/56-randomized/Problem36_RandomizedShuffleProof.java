import java.util.*;

public class Problem36_RandomizedShuffleProof {
    // Prove Fisher-Yates produces uniform distribution
    public static void main(String[] args) {
        int n = 3, trials = 600000;
        int[][] freq = new int[n][n]; // freq[position][value]
        Random rand = new Random();
        for (int t = 0; t < trials; t++) {
            int[] arr = {0, 1, 2};
            for (int i = n-1; i > 0; i--) {
                int j = rand.nextInt(i+1);
                int tmp = arr[i]; arr[i] = arr[j]; arr[j] = tmp;
            }
            for (int i = 0; i < n; i++) freq[i][arr[i]]++;
        }
        System.out.println("Position x Value frequency (should be ~" + trials/n + " each):");
        for (int i = 0; i < n; i++) System.out.println("pos " + i + ": " + Arrays.toString(freq[i]));
    }
}
