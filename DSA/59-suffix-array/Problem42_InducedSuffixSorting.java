import java.util.*;

public class Problem42_InducedSuffixSorting {
    // Concept: SA-IS induced sorting steps
    // 1. Classify each suffix as S-type or L-type
    // 2. Identify LMS (leftmost S) suffixes
    // 3. Sort LMS suffixes (recursively)
    // 4. Induce L-type, then S-type from sorted LMS

    public static char[] classifySuffixes(String s) {
        int n = s.length();
        char[] type = new char[n];
        type[n-1] = 'S';
        for (int i = n-2; i >= 0; i--)
            type[i] = s.charAt(i) < s.charAt(i+1) || (s.charAt(i) == s.charAt(i+1) && type[i+1]=='S') ? 'S' : 'L';
        return type;
    }

    public static List<Integer> findLMS(char[] type) {
        List<Integer> lms = new ArrayList<>();
        for (int i = 1; i < type.length; i++) if (type[i]=='S' && type[i-1]=='L') lms.add(i);
        return lms;
    }

    public static void main(String[] args) {
        String s = "mmiissiissiippii$";
        char[] type = classifySuffixes(s);
        System.out.println("Types: " + new String(type));
        System.out.println("LMS positions: " + findLMS(type));
    }
}
