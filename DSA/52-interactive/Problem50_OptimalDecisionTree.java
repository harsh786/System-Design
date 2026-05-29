import java.util.*;

public class Problem50_OptimalDecisionTree {
    // Build optimal binary decision tree to identify item with minimum questions
    // Items have binary attributes; find which item matches using fewest queries
    static boolean[][] items = { // 4 items, 3 attributes
        {true, false, true},
        {true, true, false},
        {false, true, true},
        {false, false, false}
    };
    static int secret = 2;
    
    static boolean queryAttribute(int attr) { return items[secret][attr]; }
    
    static int identify(int numItems, int numAttrs) {
        List<Integer> candidates = new ArrayList<>();
        for (int i = 0; i < numItems; i++) candidates.add(i);
        
        for (int attr = 0; attr < numAttrs && candidates.size() > 1; attr++) {
            boolean answer = queryAttribute(attr);
            List<Integer> next = new ArrayList<>();
            for (int c : candidates) if (items[c][attr] == answer) next.add(c);
            candidates = next;
        }
        return candidates.isEmpty() ? -1 : candidates.get(0);
    }
    
    public static void main(String[] args) {
        System.out.println("Identified item: " + identify(4, 3)); // 2
    }
}
