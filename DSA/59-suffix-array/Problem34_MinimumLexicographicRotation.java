import java.util.*;

public class Problem34_MinimumLexicographicRotation {
    // Booth's algorithm O(n)
    public static int boothMinRotation(String s) {
        String ss = s + s;
        int n = s.length();
        int[] f = new int[2*n]; Arrays.fill(f, -1);
        int k = 0;
        for (int j = 1; j < 2*n; j++) {
            int i = f[j-1-k];
            while (i != -1 && ss.charAt(j) != ss.charAt(k+i+1)) {
                if (ss.charAt(j) < ss.charAt(k+i+1)) k = j-i-1;
                i = f[i];
            }
            if (i == -1 && ss.charAt(j) != ss.charAt(k+i+1)) {
                if (ss.charAt(j) < ss.charAt(k+i+1)) k = j;
                f[j-k] = -1;
            } else f[j-k] = i+1;
        }
        return k;
    }

    public static void main(String[] args) {
        String s = "dcba";
        int k = boothMinRotation(s);
        System.out.println("Min rotation starts at: " + k);
        System.out.println("Result: " + s.substring(k) + s.substring(0, k)); // abcd... wait dcba -> adcb, badc, cbad, dcba min=adcb? no
        // Actually for "cab": min rotation = "abc" starting at index 2
        s = "cab";
        k = boothMinRotation(s);
        System.out.println(s.substring(k) + s.substring(0, k)); // abc
    }
}
