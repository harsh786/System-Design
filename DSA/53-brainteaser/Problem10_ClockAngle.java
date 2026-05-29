public class Problem10_ClockAngle {
    static double clockAngle(int h, int m) {
        double hourAngle = (h % 12) * 30 + m * 0.5;
        double minAngle = m * 6;
        double angle = Math.abs(hourAngle - minAngle);
        return Math.min(angle, 360 - angle);
    }
    
    public static void main(String[] args) {
        System.out.println("3:30 -> " + clockAngle(3, 30) + " degrees"); // 75
        System.out.println("12:00 -> " + clockAngle(12, 0) + " degrees"); // 0
        System.out.println("9:00 -> " + clockAngle(9, 0) + " degrees"); // 90 (actually 270->90)
    }
}
