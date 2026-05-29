public class Problem45_ClockHandsOverlap {
    // How many times do hour and minute hands overlap in 12 hours? 11 times.
    // Minute gains 5.5 degrees/min on hour hand. Overlap every 360/5.5 = 65.45 min
    static void findOverlaps() {
        System.out.println("Overlaps in 12 hours:");
        for (int i = 0; i < 11; i++) {
            double minutes = i * 720.0 / 11;
            int h = (int)(minutes / 60);
            double m = minutes % 60;
            System.out.printf("  %d:%05.2f%n", h, m);
        }
        System.out.println("Total: 11 overlaps in 12 hours, 22 in 24 hours");
    }
    
    public static void main(String[] args) { findOverlaps(); }
}
