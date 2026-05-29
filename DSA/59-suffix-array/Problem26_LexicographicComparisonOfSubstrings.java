import java.util.*;

public class Problem26_LexicographicComparisonOfSubstrings {
    // Compare substrings in O(1) using rank array
    int[] rank;
    String s;

    public Problem26_LexicographicComparisonOfSubstrings(String s) {
        this.s = s; int n = s.length();
        Integer[] sa = new Integer[n]; for(int i=0;i<n;i++)sa[i]=i;
        Arrays.sort(sa,(a,b)->s.substring(a).compareTo(s.substring(b)));
        rank = new int[n]; for(int i=0;i<n;i++) rank[sa[i]]=i;
    }

    // Compare suffix starting at i vs suffix starting at j
    public int compareSuffix(int i, int j) { return Integer.compare(rank[i], rank[j]); }

    public static void main(String[] args) {
        Problem26_LexicographicComparisonOfSubstrings cmp = new Problem26_LexicographicComparisonOfSubstrings("banana");
        System.out.println(cmp.compareSuffix(0, 2)); // "banana" vs "nana" -> negative
        System.out.println(cmp.compareSuffix(1, 3)); // "anana" vs "ana" -> positive (anana > ana)
    }
}
