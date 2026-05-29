import java.util.*;

/**
 * Problem 2: Shell Sort with Different Gap Sequences
 * 
 * The gap sequence significantly affects Shell Sort's performance.
 * This implements and compares multiple gap sequences:
 * - Shell's original: n/2, n/4, ..., 1
 * - Pratt's: successive numbers of form 2^p * 3^q
 * - Tokuda's: ceil((9*(9/4)^k - 4) / 5)
 * - Ciura's: empirically optimal sequence [1, 4, 10, 23, 57, 132, 301, 701]
 * 
 * Key insight: Good gap sequences avoid having gaps that are multiples of each other,
 * which ensures elements get compared against different elements at each pass.
 */
public class Problem02_ShellSortGapSequences {

    // Shell's original sequence: n/2, n/4, ..., 1
    public static List<Integer> shellGaps(int n) {
        List<Integer> gaps = new ArrayList<>();
        for (int gap = n / 2; gap > 0; gap /= 2) {
            gaps.add(gap);
        }
        return gaps;
    }

    // Ciura's empirically optimal gap sequence
    public static List<Integer> ciuraGaps(int n) {
        int[] ciura = {1, 4, 10, 23, 57, 132, 301, 701};
        List<Integer> gaps = new ArrayList<>();
        // Extend beyond 701 using 2.25x multiplier
        List<Integer> extended = new ArrayList<>();
        for (int g : ciura) extended.add(g);
        while (extended.get(extended.size() - 1) < n) {
            extended.add((int) (extended.get(extended.size() - 1) * 2.25));
        }
        for (int i = extended.size() - 1; i >= 0; i--) {
            if (extended.get(i) < n) gaps.add(extended.get(i));
        }
        return gaps;
    }

    // Tokuda's gap sequence
    public static List<Integer> tokudaGaps(int n) {
        List<Integer> gaps = new ArrayList<>();
        int k = 1;
        while (true) {
            int gap = (int) Math.ceil((9.0 * Math.pow(9.0 / 4.0, k - 1) - 4.0) / 5.0);
            if (gap >= n) break;
            gaps.add(gap);
            k++;
        }
        Collections.reverse(gaps);
        return gaps;
    }

    // Pratt's 3-smooth numbers (2^p * 3^q)
    public static List<Integer> prattGaps(int n) {
        TreeSet<Integer> set = new TreeSet<>();
        for (int p = 1; p < n; p *= 2) {
            for (int q = p; q < n; q *= 3) {
                set.add(q);
            }
        }
        List<Integer> gaps = new ArrayList<>(set.descendingSet());
        return gaps;
    }

    public static void shellSortWithGaps(int[] arr, List<Integer> gaps) {
        int n = arr.length;
        for (int gap : gaps) {
            for (int i = gap; i < n; i++) {
                int temp = arr[i];
                int j;
                for (j = i; j >= gap && arr[j - gap] > temp; j -= gap) {
                    arr[j] = arr[j - gap];
                }
                arr[j] = temp;
            }
        }
    }

    public static void main(String[] args) {
        int n = 10000;
        Random rand = new Random(42);
        int[] original = new int[n];
        for (int i = 0; i < n; i++) original[i] = rand.nextInt(100000);

        // Test each gap sequence
        String[] names = {"Shell's", "Ciura's", "Tokuda's", "Pratt's"};
        @SuppressWarnings("unchecked")
        List<Integer>[] gapSeqs = new List[]{
            shellGaps(n), ciuraGaps(n), tokudaGaps(n), prattGaps(n)
        };

        for (int t = 0; t < names.length; t++) {
            int[] arr = original.clone();
            long start = System.nanoTime();
            shellSortWithGaps(arr, gapSeqs[t]);
            long elapsed = System.nanoTime() - start;
            
            boolean sorted = true;
            for (int i = 1; i < arr.length; i++) {
                if (arr[i] < arr[i - 1]) { sorted = false; break; }
            }
            
            System.out.printf("%s gaps - Time: %.2f ms, Sorted: %b, Gaps used: %d%n",
                names[t], elapsed / 1e6, sorted, gapSeqs[t].size());
        }
    }
}
