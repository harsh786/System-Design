public class Problem43_LightBulbSwitching {
    // Variant: 3 switches, 3 bulbs in another room, one visit. Use heat!
    // Switch 1 ON for 10 min, OFF. Switch 2 ON. Enter room.
    // Hot+off=1, On=2, Cold+off=3
    static String solve() {
        return "Strategy:\n" +
            "1. Turn switch A on for 10 minutes, then turn off.\n" +
            "2. Turn switch B on.\n" +
            "3. Enter room:\n" +
            "   - Bulb ON -> Switch B\n" +
            "   - Bulb OFF but WARM -> Switch A\n" +
            "   - Bulb OFF and COLD -> Switch C";
    }
    
    public static void main(String[] args) { System.out.println(solve()); }
}
