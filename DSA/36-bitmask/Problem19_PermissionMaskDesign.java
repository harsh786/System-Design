public class Problem19_PermissionMaskDesign {
    static final int READ = 1, WRITE = 2, EXECUTE = 4, DELETE = 8, ADMIN = 16;

    public static boolean hasPermission(int userMask, int required) { return (userMask & required) == required; }
    public static int grantPermission(int userMask, int perm) { return userMask | perm; }
    public static int revokePermission(int userMask, int perm) { return userMask & ~perm; }

    public static void main(String[] args) {
        int user = READ | WRITE;
        System.out.println("Has READ: " + hasPermission(user, READ));
        System.out.println("Has EXECUTE: " + hasPermission(user, EXECUTE));
        user = grantPermission(user, EXECUTE);
        System.out.println("After grant EXECUTE: " + hasPermission(user, EXECUTE));
        user = revokePermission(user, WRITE);
        System.out.println("After revoke WRITE: " + hasPermission(user, WRITE));
    }
}
