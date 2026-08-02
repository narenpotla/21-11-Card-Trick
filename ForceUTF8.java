import java.io.PrintStream;
import java.nio.charset.StandardCharsets;

public class ForceUTF8 {
    public static void main(String[] args) {
        try {
            // Create a new PrintStream that wraps the standard output and forces UTF-8 encoding
            PrintStream out = new PrintStream(System.out, true, StandardCharsets.UTF_8);

            // Use the new PrintStream to print the symbol
            out.println("Forcing UTF-8 output: ♤");

        } catch (Exception e) {
            System.out.println("An error occurred: " + e.getMessage());
        }
    }
}