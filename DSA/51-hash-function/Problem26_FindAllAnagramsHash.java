import java.util.*;

public class Problem26_FindAllAnagramsHash {
    public List<Integer> findAnagrams(String s, String p) {
        List<Integer> result = new ArrayList<>();
        if (s.length() < p.length()) return result;
        int[] pCount = new int[26], sCount = new int[26];
        for (char c : p.toCharArray()) pCount[c - 'a']++;
        for (int i = 0; i < s.length(); i++) {
            sCount[s.charAt(i) - 'a']++;
            if (i >= p.length()) sCount[s.charAt(i - p.length()) - 'a']--;
            if (Arrays.equals(sCount, pCount)) result.add(i - p.length() + 1);
        }
        return result;
    }

    public static void main(String[] args) {
        Problem26_FindAllAnagramsHash sol = new Problem26_FindAllAnagramsHash();
        System.out.println(sol.findAnagrams("cbaebabacd", "abc")); // [0, 6]
    }
}
