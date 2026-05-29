import java.util.*;

public class Problem08_IsomorphicStrings {
    public boolean isIsomorphic(String s, String t) {
        if (s.length() != t.length()) return false;
        Map<Character, Character> sToT = new HashMap<>(), tToS = new HashMap<>();
        for (int i = 0; i < s.length(); i++) {
            char a = s.charAt(i), b = t.charAt(i);
            if (sToT.containsKey(a) && sToT.get(a) != b) return false;
            if (tToS.containsKey(b) && tToS.get(b) != a) return false;
            sToT.put(a, b);
            tToS.put(b, a);
        }
        return true;
    }

    public static void main(String[] args) {
        Problem08_IsomorphicStrings sol = new Problem08_IsomorphicStrings();
        System.out.println(sol.isIsomorphic("egg", "add")); // true
        System.out.println(sol.isIsomorphic("foo", "bar")); // false
    }
}
