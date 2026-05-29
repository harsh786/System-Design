import java.util.*;

public class Problem50_BlueRedHackenbushIntro {
    // Blue-Red Hackenbush: Combinatorial game on a graph. Edges colored Blue/Red.
    // Left (Blue) removes blue edges, Right (Red) removes red edges.
    // If edge removal disconnects from ground, those edges also removed.
    // Value: chain of b blue and r red edges has value b - r (simplified).
    // For stalks (chains), game value = sum of individual edge values.
    
    // Simplified: compute game value of a Hackenbush string (chain from ground)
    // Blue = +1, Red = -1 for each edge. Positive = Left wins, Negative = Right wins.
    
    public double hackenbushChainValue(char[] edges) {
        // For a single chain: convert to binary fraction using Berlekamp's sign expansion
        // Simplified: just sum for introduction
        double val = 0;
        for (char e : edges) {
            if (e == 'B') val += 1;
            else if (e == 'R') val -= 1;
        }
        return val;
    }
    
    // Multiple independent chains: sum their values
    public double hackenbushGameValue(char[][] chains) {
        double total = 0;
        for (char[] chain : chains) total += hackenbushChainValue(chain);
        return total;
    }
    
    public String winner(double value) {
        if (value > 0) return "Left (Blue) wins";
        if (value < 0) return "Right (Red) wins";
        return "Second player wins";
    }
    
    public static void main(String[] args) {
        Problem50_BlueRedHackenbushIntro sol = new Problem50_BlueRedHackenbushIntro();
        char[][] game = {
            {'B', 'B', 'R'},  // chain 1: value = 1
            {'R', 'R'},       // chain 2: value = -2
            {'B', 'B', 'B'}   // chain 3: value = 3
        };
        double val = sol.hackenbushGameValue(game);
        System.out.println("Game value: " + val);      // 2.0
        System.out.println("Winner: " + sol.winner(val)); // Left wins
        
        char[][] game2 = {{'B','R'}, {'B','R'}};
        double val2 = sol.hackenbushGameValue(game2);
        System.out.println("Game2 value: " + val2 + " -> " + sol.winner(val2)); // 0 -> second player
    }
}
