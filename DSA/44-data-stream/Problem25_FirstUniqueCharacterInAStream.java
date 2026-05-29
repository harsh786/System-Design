import java.util.*;

public class Problem25_FirstUniqueCharacterInAStream {
    // First Unique Character in a stream using LinkedHashSet + HashSet.
    
    Set<Character> unique = new LinkedHashSet<>();
    Set<Character> seen = new HashSet<>();
    
    public void add(char c) {
        if (!seen.contains(c)) { seen.add(c); unique.add(c); }
        else unique.remove(c);
    }
    
    public char firstUnique() {
        return unique.isEmpty() ? '#' : unique.iterator().next();
    }
    
    public static void main(String[] args) {
        Problem25_FirstUniqueCharacterInAStream sol = new Problem25_FirstUniqueCharacterInAStream();
        for (char c : "aabcbde".toCharArray()) {
            sol.add(c);
            System.out.println("After '" + c + "': " + sol.firstUnique());
        }
    }
}
