import java.util.*;

public class Problem08_SparseSearch {
    // Search in sparse array (strings with empty strings interspersed)
    static String[] arr = {"at","","","","ball","","","car","","","dad","",""};
    
    static int sparseSearch(String target) {
        int lo = 0, hi = arr.length - 1;
        while (lo <= hi) {
            int mid = lo + (hi - lo) / 2;
            int m = mid;
            // Find nearest non-empty
            int left = mid - 1, right = mid + 1;
            if (arr[mid].isEmpty()) {
                while (left >= lo && right <= hi) {
                    if (!arr[left].isEmpty()) { mid = left; break; }
                    if (!arr[right].isEmpty()) { mid = right; break; }
                    left--; right++;
                }
                if (arr[mid].isEmpty()) return -1;
            }
            int cmp = arr[mid].compareTo(target);
            if (cmp == 0) return mid;
            else if (cmp < 0) lo = mid + 1;
            else hi = mid - 1;
        }
        return -1;
    }
    
    public static void main(String[] args) {
        System.out.println("Search 'ball': " + sparseSearch("ball")); // 4
        System.out.println("Search 'car': " + sparseSearch("car")); // 7
    }
}
