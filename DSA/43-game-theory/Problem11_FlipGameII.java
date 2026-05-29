import java.util.*;

public class Problem11_FlipGameII {
    // 294. Flip Game II: String of '+' and '-'. Player flips "++" to "--". 
    // Player who can't move loses. Can first player guarantee a win?
    
    Map<String, Boolean> memo = new HashMap<>();
    
    public boolean canWin(String currentState) {
        if (memo.containsKey(currentState)) return memo.get(currentState);
        for (int i = 0; i < currentState.length() - 1; i++) {
            if (currentState.charAt(i) == '+' && currentState.charAt(i+1) == '+') {
                String next = currentState.substring(0,i) + "--" + currentState.substring(i+2);
                if (!canWin(next)) { memo.put(currentState, true); return true; }
            }
        }
        memo.put(currentState, false);
        return false;
    }
    
    public static void main(String[] args) {
        Problem11_FlipGameII sol = new Problem11_FlipGameII();
        System.out.println(sol.canWin("++++"));  // true
        System.out.println(sol.canWin("+++++"));  // false
    }
}
