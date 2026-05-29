import java.util.*;

public class Problem09_WordPattern {
    public boolean wordPattern(String pattern, String s) {
        String[] words = s.split(" ");
        if (pattern.length() != words.length) return false;
        Map<Character, String> pToW = new HashMap<>();
        Map<String, Character> wToP = new HashMap<>();
        for (int i = 0; i < pattern.length(); i++) {
            char c = pattern.charAt(i);
            String w = words[i];
            if (pToW.containsKey(c) && !pToW.get(c).equals(w)) return false;
            if (wToP.containsKey(w) && wToP.get(w) != c) return false;
            pToW.put(c, w);
            wToP.put(w, c);
        }
        return true;
    }

    public static void main(String[] args) {
        Problem09_WordPattern sol = new Problem09_WordPattern();
        System.out.println(sol.wordPattern("abba", "dog cat cat dog")); // true
    }
}
