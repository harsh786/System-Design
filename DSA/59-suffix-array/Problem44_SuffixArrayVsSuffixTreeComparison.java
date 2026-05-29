import java.util.*;

public class Problem44_SuffixArrayVsSuffixTreeComparison {
    // Comparison of Suffix Array vs Suffix Tree
    public static void main(String[] args) {
        System.out.println("=== Suffix Array vs Suffix Tree Comparison ===");
        System.out.println();
        System.out.println("Feature          | Suffix Array          | Suffix Tree");
        System.out.println("-----------------|-----------------------|----------------------");
        System.out.println("Space            | O(n) integers         | O(n) but ~20x more");
        System.out.println("Construction     | O(n) or O(n log n)    | O(n) (Ukkonen's)");
        System.out.println("Pattern search   | O(m log n) or O(m+log n)| O(m)");
        System.out.println("LCP queries      | Need LCP array + RMQ  | Tree edges");
        System.out.println("Cache friendly   | Yes (array)           | No (pointers)");
        System.out.println("Implementation   | Simpler               | Complex");
        System.out.println("Memory overhead  | ~4n-8n bytes          | ~60n-80n bytes");
        System.out.println();

        // Demo: both solve same problem
        String s = "banana";
        int n = s.length();
        Integer[] sa = new Integer[n]; for(int i=0;i<n;i++)sa[i]=i;
        Arrays.sort(sa,(a,b)->s.substring(a).compareTo(s.substring(b)));
        System.out.println("Suffix Array of '" + s + "': " + Arrays.toString(sa));
    }
}
