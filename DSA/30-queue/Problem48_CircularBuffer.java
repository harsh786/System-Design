public class Problem48_CircularBuffer {
    int[] buf; int head = 0, tail = 0, size = 0, cap;
    Problem48_CircularBuffer(int cap) { this.cap = cap; buf = new int[cap]; }
    boolean write(int val) { if (isFull()) return false; buf[tail] = val; tail = (tail + 1) % cap; size++; return true; }
    int read() { if (isEmpty()) return -1; int val = buf[head]; head = (head + 1) % cap; size--; return val; }
    void overwrite(int val) { if (isFull()) { head = (head + 1) % cap; size--; } write(val); }
    boolean isEmpty() { return size == 0; }
    boolean isFull() { return size == cap; }
    public static void main(String[] args) {
        Problem48_CircularBuffer cb = new Problem48_CircularBuffer(3);
        cb.write(1); cb.write(2); cb.write(3);
        System.out.println(cb.write(4)); // false
        cb.overwrite(4);
        System.out.println(cb.read()); // 2
        System.out.println(cb.read()); // 3
        System.out.println(cb.read()); // 4
    }
}
