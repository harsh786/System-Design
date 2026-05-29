/**
 * Problem 18: Angle Between Hands of a Clock
 * Given hour and minutes, find the smaller angle between hour and minute hands.
 *
 * Approach: Calculate positions. Minute hand: 6*min degrees. Hour hand: 30*hour + 0.5*min.
 * Time Complexity: O(1)
 * Space Complexity: O(1)
 *
 * Production Analogy: Like computing phase differences in signal processing
 * or angular distance in geospatial calculations.
 */
public class Problem18_AngleBetweenHandsOfClock {

    public static double angleClock(int hour, int minutes) {
        double minuteAngle = 6.0 * minutes;
        double hourAngle = 30.0 * (hour % 12) + 0.5 * minutes;
        double diff = Math.abs(hourAngle - minuteAngle);
        return Math.min(diff, 360 - diff);
    }

    public static void main(String[] args) {
        System.out.println(angleClock(12, 30)); // 165.0
        System.out.println(angleClock(3, 30));  // 75.0
        System.out.println(angleClock(3, 15));  // 7.5
        System.out.println(angleClock(12, 0));  // 0.0
        System.out.println(angleClock(6, 0));   // 180.0
    }
}
