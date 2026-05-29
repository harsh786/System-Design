import java.util.*;

/**
 * Problem 8: Shell Sort Stability Analysis
 * 
 * Shell Sort is NOT stable. Elements with equal keys can be rearranged
 * because distant exchanges can swap equal elements past each other.
 * 
 * Stability matters when:
 * - Sorting by multiple keys (e.g., sort by name then by age)
 * - Preserving original order of equal elements
 * 
 * This demonstrates the instability and shows a workaround using
 * index decoration (Schwartzian transform).
 */
public class Problem08_ShellSortStability {

    static class Record {
        int key;
        int originalIndex;
        String label;

        Record(int key, int originalIndex, String label) {
            this.key = key;
            this.originalIndex = originalIndex;
            this.label = label;
        }

        @Override
        public String toString() {
            return label + "(" + key + ")";
        }
    }

    // Standard unstable Shell Sort on records (by key)
    public static void shellSortUnstable(Record[] arr) {
        int n = arr.length;
        int gap = 1;
        while (gap < n / 3) gap = 3 * gap + 1;
        while (gap >= 1) {
            for (int i = gap; i < n; i++) {
                Record temp = arr[i];
                int j = i;
                while (j >= gap && arr[j - gap].key > temp.key) {
                    arr[j] = arr[j - gap];
                    j -= gap;
                }
                arr[j] = temp;
            }
            gap /= 3;
        }
    }

    // Stable Shell Sort using index decoration
    // Comparison: first by key, then by original index (to preserve stability)
    public static void shellSortStable(Record[] arr) {
        int n = arr.length;
        int gap = 1;
        while (gap < n / 3) gap = 3 * gap + 1;
        while (gap >= 1) {
            for (int i = gap; i < n; i++) {
                Record temp = arr[i];
                int j = i;
                while (j >= gap && compareStable(arr[j - gap], temp) > 0) {
                    arr[j] = arr[j - gap];
                    j -= gap;
                }
                arr[j] = temp;
            }
            gap /= 3;
        }
    }

    private static int compareStable(Record a, Record b) {
        if (a.key != b.key) return Integer.compare(a.key, b.key);
        return Integer.compare(a.originalIndex, b.originalIndex);
    }

    public static boolean isStable(Record[] arr) {
        for (int i = 1; i < arr.length; i++) {
            if (arr[i].key == arr[i-1].key) {
                if (arr[i].originalIndex < arr[i-1].originalIndex) return false;
            }
        }
        return true;
    }

    public static void main(String[] args) {
        // Create records with duplicate keys
        Record[] records = {
            new Record(3, 0, "A"), new Record(1, 1, "B"), new Record(3, 2, "C"),
            new Record(2, 3, "D"), new Record(1, 4, "E"), new Record(2, 5, "F"),
            new Record(3, 6, "G"), new Record(1, 7, "H")
        };

        System.out.println("Original: " + Arrays.toString(records));

        // Unstable sort
        Record[] unstable = records.clone();
        shellSortUnstable(unstable);
        System.out.println("Unstable: " + Arrays.toString(unstable));
        System.out.println("Is stable? " + isStable(unstable));

        // Reset and do stable sort
        Record[] stable = records.clone();
        shellSortStable(stable);
        System.out.println("Stable:   " + Arrays.toString(stable));
        System.out.println("Is stable? " + isStable(stable));
        
        System.out.println("\nConclusion: Shell Sort is inherently unstable.");
        System.out.println("Workaround: Use index decoration for O(1) extra per element.");
    }
}
