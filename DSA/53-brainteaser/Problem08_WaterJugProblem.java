import java.util.*;

public class Problem08_WaterJugProblem {
    // Can measure exactly z liters with jugs of capacity x and y?
    // Yes iff z is multiple of gcd(x,y) and z <= x+y
    static boolean canMeasure(int x, int y, int z) {
        if (z > x + y) return false;
        if (z == 0) return true;
        return z % gcd(x, y) == 0;
    }
    
    static int gcd(int a, int b) { return b == 0 ? a : gcd(b, a % b); }
    
    public static void main(String[] args) {
        System.out.println("3,5 -> 4: " + canMeasure(3, 5, 4)); // true
        System.out.println("2,6 -> 5: " + canMeasure(2, 6, 5)); // false
    }
}
