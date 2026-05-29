import java.util.*;

public class Problem07_SmallestCyclicShift {
    // Booth's algorithm or suffix array on doubled string
    public static String smallestRotation(String s) {
        String doubled = s + s;
        int n = s.length();
        Integer[] sa = new Integer[doubled.length()];
        for (int i = 0; i < doubled.length(); i++) sa[i] = i;
        Arrays.sort(sa, (a, b) -> doubled.substring(a).compareTo(doubled.substring(b)));
        for (int idx : sa) if (idx < n) return doubled.substring(idx, idx + n);
        return s;
    }

    public static void main(String[] args) {
        System.out.println(smallestRotation("cab")); // abc
        System.out.println(smallestRotation("bcda")); // abcd... no, bcda rotations: bcda, cdab, dabc, abcd -> abcd
        System.out.println(smallestRotation("baab")); // aabb
    }
}
