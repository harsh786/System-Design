public class Problem25_BinarySearchRecursive {
    public static int binarySearch(int[] arr, int target, int l, int r) {
        if (l > r) return -1;
        int mid = (l + r) / 2;
        if (arr[mid] == target) return mid;
        if (arr[mid] < target) return binarySearch(arr, target, mid + 1, r);
        return binarySearch(arr, target, l, mid - 1);
    }
    public static void main(String[] args) {
        int[] arr = {1, 3, 5, 7, 9, 11};
        System.out.println(binarySearch(arr, 7, 0, arr.length - 1)); // 3
        System.out.println(binarySearch(arr, 4, 0, arr.length - 1)); // -1
    }
}
