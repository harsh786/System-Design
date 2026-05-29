import java.util.*;

public class Problem18_ZumaGame {
    // 488. Zuma Game: Insert balls to clear the board. Find min balls needed or -1.
    
    Map<String, Integer> memo = new HashMap<>();
    
    public int findMinStep(String board, String hand) {
        char[] h = hand.toCharArray();
        Arrays.sort(h);
        int res = dfs(board, new String(h));
        return res == Integer.MAX_VALUE ? -1 : res;
    }
    
    private int dfs(String board, String hand) {
        if (board.isEmpty()) return 0;
        if (hand.isEmpty()) return Integer.MAX_VALUE;
        String key = board + "#" + hand;
        if (memo.containsKey(key)) return memo.get(key);
        
        int res = Integer.MAX_VALUE;
        for (int i = 0; i < board.length(); i++) {
            for (int j = 0; j < hand.length(); j++) {
                if (board.charAt(i) != hand.charAt(j)) continue;
                if (j > 0 && hand.charAt(j) == hand.charAt(j-1)) continue; // skip dup
                String newBoard = clean(board.substring(0,i) + hand.charAt(j) + board.substring(i));
                String newHand = hand.substring(0,j) + hand.substring(j+1);
                int sub = dfs(newBoard, newHand);
                if (sub != Integer.MAX_VALUE) res = Math.min(res, sub + 1);
            }
        }
        memo.put(key, res);
        return res;
    }
    
    private String clean(String s) {
        StringBuilder sb = new StringBuilder(s);
        boolean changed = true;
        while (changed) {
            changed = false;
            for (int i = 0; i < sb.length(); ) {
                int j = i;
                while (j < sb.length() && sb.charAt(j) == sb.charAt(i)) j++;
                if (j - i >= 3) { sb.delete(i, j); changed = true; }
                else i = j;
            }
        }
        return sb.toString();
    }
    
    public static void main(String[] args) {
        Problem18_ZumaGame sol = new Problem18_ZumaGame();
        System.out.println(sol.findMinStep("WRRBBW", "RB")); // -1
        System.out.println(sol.findMinStep("WWRRBBWW", "WRBRW")); // 2
    }
}
